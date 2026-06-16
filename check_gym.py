import requests
import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
THRESHOLD = int(os.environ.get("THRESHOLD", "30"))

API_URL    = "https://bdcsc.cyc.org.tw/api"
STATE_FILE = "state.json"
TZ = ZoneInfo("Asia/Taipei")

REMIND_EVERY_N = 1  # 每幾次執行提醒一次（4次×5分鐘=20分鐘）

def get_gym_count():
    resp = requests.get(API_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return int(data["gym"][0]), int(data["gym"][1])

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    if resp.status_code == 200:
        logging.info(f"📨 送出：{message[:40]}…")
    else:
        logging.error(f"❌ 失敗：{resp.text}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"is_low": False, "ticks_since_notify": 0}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def in_active_window(now):
    start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=23, minute=0, second=0, microsecond=0)
    return start <= now <= end

def main():
    now = datetime.now(TZ)
    now_str = now.strftime("%H:%M")

    if not in_active_window(now):
        logging.info(f"[{now_str}] 不在通知時段，跳過")
        return

    state = load_state()
    is_low = state.get("is_low", False)
    ticks  = state.get("ticks_since_notify", 0)

    try:
        count, capacity = get_gym_count()
    except Exception as e:
        logging.warning(f"⚠️ 抓取失敗：{e}")
        return

    logging.info(f"[{now_str}] 健身房：{count}/{capacity} 人，is_low={is_low}，ticks={ticks}")

    if count < THRESHOLD:
        ticks += 1
        if not is_low or ticks >= REMIND_EVERY_N:
            send_telegram(
                f"🟢 <b>現在可以去健身房了！</b>\n\n"
                f"🕐 時間：{now_str}\n"
                f"👥 目前人數：<b>{count} 人</b>（容留 {capacity} 人）\n\n"
                f"現在很空，快去 💪"
            )
            ticks = 0
        state["is_low"] = True
        state["ticks_since_notify"] = ticks
        save_state(state)

    else:
        if is_low:
            send_telegram(
                f"🔴 <b>健身房人數回升</b>\n\n"
                f"🕐 時間：{now_str}\n"
                f"👥 目前人數：<b>{count} 人</b>（已超過 {THRESHOLD} 人）"
            )
        state["is_low"] = False
        state["ticks_since_notify"] = 0
        save_state(state)

if __name__ == "__main__":
    main()