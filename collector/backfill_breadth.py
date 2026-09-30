"""回補上市／上櫃每日「上漲、下跌、漲停、跌停」家數到 history.csv（市場動能量表用）。

來源：TWSE MI_INDEX（type=MS，「漲跌證券數合計」表的「股票」欄）與 TPEX afterTrading/highlight。
順帶補 taiex_volume 缺月（FMTQIK 按月）。可中斷續跑（進度存 data/backfill_breadth.progress.json）。

用法：.venv/bin/python -m collector.backfill_breadth [--since 2024-07-08] [--sleep 0.8]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from collector import fetchers
from collector.storage import load_history, upsert

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"
PROGRESS = ROOT / "data" / "backfill_breadth.progress.json"
TWSE_KEYS = ("twse_up", "twse_down", "twse_limit_up", "twse_limit_down")
TPEX_KEYS = ("tpex_up", "tpex_down", "tpex_limit_up", "tpex_limit_down")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-07-08")
    ap.add_argument("--sleep", type=float, default=0.8)
    args = ap.parse_args()

    hist = load_history(HISTORY)
    days = [d for d, _ in hist["taiex_close"] if d >= args.since]
    done = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {}
    print(f"{len(days)} 個交易日，已有進度 {len(done)}", flush=True)

    for n, d in enumerate(days, 1):
        if d in done:
            continue
        rec = {}
        ymd = d.replace("-", "")
        try:
            r = fetchers.fetch_breadth_counts(ymd)
            if r:
                rec.update(zip(TWSE_KEYS, r[1:]))
        except Exception as e:
            print(f"{d} TWSE 失敗 {type(e).__name__}: {e}", flush=True)
        time.sleep(args.sleep)
        try:
            r = fetchers.fetch_tpex_counts(d.replace("-", "/"))
            if r:
                rec.update(zip(TPEX_KEYS, r[1:]))
        except Exception as e:
            print(f"{d} TPEX 失敗 {type(e).__name__}: {e}", flush=True)
        time.sleep(args.sleep)
        done[d] = rec
        PROGRESS.write_text(json.dumps(done))
        if n % 20 == 0:
            print(f"[{n}/{len(days)}] {d} {rec}", flush=True)

    for key in TWSE_KEYS + TPEX_KEYS:
        pts = [(d, v) for d, rec in sorted(done.items()) if key in rec for v in [rec[key]]]
        if pts:
            upsert(HISTORY, key, pts)
            print(f"{key}: {len(pts)} 筆 {pts[0][0]} → {pts[-1][0]}", flush=True)

    # taiex_volume 缺月回補（FMTQIK 整月）
    have = {d for d, _ in hist.get("taiex_volume", [])}
    missing_months = sorted({d[:7] for d in days} - {d[:7] for d in have})
    for ym in missing_months:
        try:
            month = fetchers.fetch_taiex_month(ym.replace("-", "") + "01")
            if month and month["volumes"]:
                upsert(HISTORY, "taiex_volume", month["volumes"])
                upsert(HISTORY, "taiex_close", month["closes"])
                print(f"taiex_volume 補 {ym}: {len(month['volumes'])} 筆", flush=True)
        except Exception as e:
            print(f"taiex_volume {ym} 失敗 {type(e).__name__}: {e}", flush=True)
        time.sleep(args.sleep)
    print("完成", flush=True)


if __name__ == "__main__":
    sys.exit(main())
