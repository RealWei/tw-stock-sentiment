"""每日收集主程式：抓資料 → 更新 history.csv → 產出 docs/data/*.json → 判斷通知。"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import fetchers
from collector.notify import notification_message, send_telegram, should_notify
from collector.pipeline import (
    INDICATORS,
    composite_series,
    daily_snapshot,
    derive_indicator_series,
)
from collector.storage import load_history, upsert

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"
STATE = ROOT / "data" / "state.json"
DOCS_DATA = ROOT / "docs" / "data"

TAIPEI = timezone(timedelta(hours=8))
FAILURE_ALERT_THRESHOLD = 2


def fetch_all(today_yyyymmdd):
    """抓所有每日資料源，回傳 {raw_name: [(date, value)]} 與失敗清單。"""
    updates, failures = {}, []

    def attempt(name, fn):
        try:
            return fn()
        except Exception as exc:  # 單一來源失敗不中斷其他來源
            failures.append(f"{name}: {exc}")
            return None

    margin = attempt("margin_balance", lambda: fetchers.fetch_margin_balance(today_yyyymmdd))
    if margin:
        updates["margin_balance"] = [margin]

    breadth = attempt("breadth_ratio", lambda: fetchers.fetch_breadth(today_yyyymmdd))
    if breadth:
        date, up, down = breadth
        if up + down:
            updates["breadth_ratio"] = [(date, up / (up + down))]

    closes = attempt("taiex_close", lambda: fetchers.fetch_taiex_closes(today_yyyymmdd))
    if closes:
        updates["taiex_close"] = closes

    pc = attempt("pc_oi_ratio", fetchers.fetch_put_call_oi_ratio)
    if pc:
        updates["pc_oi_ratio"] = pc

    foreign = attempt("foreign_net_oi", fetchers.fetch_foreign_futures_net_oi)
    if foreign:
        updates["foreign_net_oi"] = [foreign]

    return updates, failures


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"zone": None, "consecutive_failures": 0}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def write_outputs(snapshot, derived):
    DOCS_DATA.mkdir(parents=True, exist_ok=True)

    latest = {
        "date": snapshot["date"],
        "composite": snapshot["composite"],
        "zone": snapshot["zone"],
        "indicators": [
            {
                "id": ind_id,
                "name": name,
                "invert": invert,
                "cadence": cadence,
                "value": snapshot["values"][ind_id],
                "score": snapshot["scores"][ind_id],
                "updated": snapshot["updated"][ind_id],
            }
            for ind_id, (name, invert, cadence) in INDICATORS.items()
        ],
    }
    (DOCS_DATA / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=1)
    )

    series = {
        "composite": composite_series(derived),
        "indicators": {
            ind_id: derived.get(ind_id, []) for ind_id in INDICATORS
        },
    }
    (DOCS_DATA / "series.json").write_text(json.dumps(series, ensure_ascii=False))


def main():
    now = datetime.now(TAIPEI)
    today = now.strftime("%Y%m%d")
    print(f"收集 {now:%Y-%m-%d} 台北時間 {now:%H:%M}")

    updates, failures = fetch_all(today)
    for name, points in updates.items():
        upsert(HISTORY, name, points)
        print(f"  {name}: +{len(points)} 筆（最新 {points[-1][0]}）")
    for f in failures:
        print(f"  失敗 {f}", file=sys.stderr)

    raw = load_history(HISTORY)
    if not raw:
        print("尚無任何歷史資料", file=sys.stderr)
        sys.exit(1)

    derived = derive_indicator_series(raw)
    snapshot = daily_snapshot(derived, now.strftime("%Y-%m-%d"))
    write_outputs(snapshot, derived)
    comp = snapshot["composite"]
    print(f"總分: {comp:.1f} ({snapshot['zone']})" if comp is not None else "總分: 資料不足")

    state = load_state()
    if failures:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= FAILURE_ALERT_THRESHOLD:
            send_telegram(
                f"⚠️ 台股儀表板資料收集已連續 {state['consecutive_failures']} 天失敗：\n"
                + "\n".join(failures)
            )
    else:
        state["consecutive_failures"] = 0

    if snapshot["zone"] is not None and should_notify(state["zone"], snapshot["zone"]):
        send_telegram(notification_message(snapshot))
        print(f"已通知：{state['zone']} → {snapshot['zone']}")
    if snapshot["zone"] is not None:
        state["zone"] = snapshot["zone"]
    save_state(state)


if __name__ == "__main__":
    main()
