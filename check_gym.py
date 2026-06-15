import requests
import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
THRESHOLD = int(os.environ.get("THRESHOLD", "30"))
API_URL    = "https://bdcsc.cyc.org.tw/api"
STATE_FILE = "state.json"
TZ = ZoneInfo("Asia/Taipei")
REMIND_INTERVAL_MIN = 20  # 低於門檻時的重複提醒間隔(分鐘)

def get_gym_count():
    resp = requests.get(API_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    count    = int(data["gym"][0])
    capacity = int(data["gym"][1])
    return count, capacity

def send_telegram(message: str):
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
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"notified_low": False, "last_notify": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def in_active_window(now: datetime) -> bool:
    start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=20, minute=40, second=0, microsecond=0)
    return start <= now <= end

def main():
    now = datetime.now(TZ)
    now_str = now.strftime("%H:%M")

    if not in_active_window(now):
        logging.info(f"[{now_str}] 不在通知時段(07:00-20:40)，跳過")
        return

    state = load_state()
    notified_low = state.get("notified_low", False)
    last_notify_str = state.get("last_notify")
    last_notify = datetime.fromisoformat(last_notify_str) if last_notify_str else None

    try:
        count, capacity = get_gym_count()
    except Exception as e:
        logging.warning(f"⚠️  抓取資料失敗：{e}")
        return

    logging.info(f"[{now_str}] 健身房目前：{count}/{capacity} 人")

    if count < THRESHOLD:
        should_notify = False
        if not notified_low:
            should_notify = True
        elif last_notify is None or (now - last_notify).total_seconds() >= REMIND_INTERVAL_MIN * 60:
            should_notify = True

        if should_notify:
            send_telegram(
                f"🟢 <b>現在可以去健身房了！</b>\n\n"
                f"🕐 時間：{now_str}\n"
                f"👥 目前人數：<b>{count} 人</b>（容留 {capacity} 人）\n\n"
                f"現在很空，快去 💪"
            )
            state["notified_low"] = True
            state["last_notify"] = now.isoformat()
            save_state(state)
        else:
            logging.info("仍低於門檻，但尚未到下次提醒時間")

    elif notified_low:
        send_telegram(
            f"🔴 <b>健身房人數回升</b>\n\n"
            f"🕐 時間：{now_str}\n"
            f"👥 目前人數：<b>{count} 人</b>（已超過 {THRESHOLD} 人）"
        )
        state["notified_low"] = False
        state["last_notify"] = None
        save_state(state)
    else:
        logging.info("狀態未改變，不發送通知")

if __name__ == "__main__":
    main()