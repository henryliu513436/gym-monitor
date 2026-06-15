import requests
import os
import json
import logging
from datetime import datetime

# ─── 設定 logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)

# ─── 從環境變數讀取設定 ──────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
THRESHOLD = int(os.environ.get("THRESHOLD", "30"))

API_URL    = "https://bdcsc.cyc.org.tw/api"
STATE_FILE = "state.json"


def get_gym_count():
    """從八德運動中心 API 取得健身房目前人數與容留上限"""
    resp = requests.get(API_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    count    = int(data["gym"][0])
    capacity = int(data["gym"][1])
    return count, capacity


def send_telegram(message: str):
    """透過 Telegram Bot 發送訊息"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10
    )
    if resp.status_code == 200:
        logging.info(f"📨 Telegram 送出：{message[:40]}…")
    else:
        logging.error(f"❌ Telegram 送出失敗：{resp.text}")


def load_state():
    """讀取上次的通知狀態，檔案不存在則視為「未通知」"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"notified_low": False}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main():
    state = load_state()
    notified_low = state.get("notified_low", False)

    try:
        count, capacity = get_gym_count()
    except Exception as e:
        logging.warning(f"⚠️  抓取資料失敗：{e}")
        return  # 失敗就跳過這次，不更動狀態

    now = datetime.now().strftime("%H:%M")
    logging.info(f"[{now}] 健身房目前：{count}/{capacity} 人")

    if count < THRESHOLD and not notified_low:
        send_telegram(
            f"🟢 <b>現在可以去健身房了！</b>\n\n"
            f"🕐 時間：{now}\n"
            f"👥 目前人數：<b>{count} 人</b>（容留 {capacity} 人）\n\n"
            f"現在很空，快去 💪"
        )
        state["notified_low"] = True
        save_state(state)

    elif count >= THRESHOLD and notified_low:
        send_telegram(
            f"🔴 <b>健身房人數回升</b>\n\n"
            f"🕐 時間：{now}\n"
            f"👥 目前人數：<b>{count} 人</b>（已超過 {THRESHOLD} 人）"
        )
        state["notified_low"] = False
        save_state(state)

    else:
        # 狀態沒變化，不通知，也不需要重寫 state 檔
        logging.info("狀態未改變，不發送通知")


if __name__ == "__main__":
    main()
