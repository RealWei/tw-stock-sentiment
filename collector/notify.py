"""Telegram 通知：燈號狀態改變時發送。"""

import os

import requests

from collector.pipeline import INDICATORS

EXTREME_ZONES = ("overheat", "cold")
SINGLE_INDICATOR_ALERT = 95.0  # 單項指標列入訊息的百分位門檻

ZONE_TEXT = {
    "overheat": "🔴 市場過熱，留意減碼時機",
    "cold": "🟢 市場過冷，留意加碼時機",
    "neutral": "⚪ 回到中性區間",
}


def should_notify(prev_zone, new_zone):
    """燈號改變才通知；首次執行只在直接落於極端區時通知。"""
    if prev_zone is None:
        return new_zone in EXTREME_ZONES
    return new_zone != prev_zone


def notification_message(snapshot):
    lines = [
        f"台股情緒指標 {snapshot['date']}",
        f"總分 {snapshot['composite']:.0f}/100 — "
        + ("過熱" if snapshot["zone"] == "overheat" else "過冷" if snapshot["zone"] == "cold" else "中性"),
        ZONE_TEXT[snapshot["zone"]],
    ]
    if snapshot.get("greed") is not None and snapshot.get("fear") is not None:
        lines.insert(2, f"過熱計 {snapshot['greed']:.0f}（≥80 過熱）／恐慌計 {snapshot['fear']:.0f}（≤15 過冷）")

    extremes = []
    for ind_id, score in snapshot["scores"].items():
        if score is None:
            continue
        if score >= SINGLE_INDICATOR_ALERT or score <= 100 - SINGLE_INDICATOR_ALERT:
            name = INDICATORS[ind_id][0]
            extremes.append(f"・{name}：{snapshot['values'][ind_id]:.2f}（{score:.0f} 分）")
    if extremes:
        lines.append("極端單項指標：")
        lines.extend(extremes)

    return "\n".join(lines)


def send_telegram(message):
    """需要環境變數 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID；未設定則跳過。"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram 未設定，略過通知")
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=30,
    )
    resp.raise_for_status()
    return True
