import requests
import time
import os
import logging
from datetime import datetime

# ─── 設定 logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)

# ─── 從環境變數讀取設定 ──────────────────────────────────────────
BOT_TOKEN      = os.environ["BOT_TOKEN"]       # Telegram Bot Token
CHAT_ID        = os.environ["CHAT_ID"]         # 你的 Telegram Chat ID
THRESHOLD      = int(os.environ.get("THRESHOLD", "30"))        # 人數門檻，預設 30
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))   # 檢查間隔（秒），預設 60

API_URL = "https://bdcsc.cyc.org.tw/api"

# ─── 狀態追蹤 ───────────────────────────────────────────────────
notified_low = False   # True = 已送出「低於門檻」通知，還沒送過「回升」通知


def get_gym_count():
    """從八德運動中心 API 取得健身房目前人數與容留上限"""
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        count    = int(data["gym"][0])
        capacity = int(data["gym"][1])
        return count, capacity
    except Exception as e:
        logging.warning(f"⚠️  抓取資料失敗：{e}")
        return None, None


def send_telegram(message: str):
    """透過 Telegram Bot 發送訊息"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        if resp.status_code == 200:
            logging.info(f"📨 Telegram 送出：{message[:40]}…")
        else:
            logging.error(f"❌ Telegram 送出失敗：{resp.text}")
    except Exception as e:
        logging.error(f"❌ 發送 Telegram 時發生錯誤：{e}")


def main():
    global notified_low
    logging.info("🏋️  八德健身房監控啟動！")
    send_telegram(
        "🤖 <b>監控機器人已啟動</b>\n\n"
        f"每 {CHECK_INTERVAL} 秒檢查一次八德健身房人數\n"
        f"低於 <b>{THRESHOLD} 人</b>時會立即通知你 💪"
    )

    while True:
        count, capacity = get_gym_count()
        now = datetime.now().strftime("%H:%M")

        if count is not None:
            logging.info(f"[{now}] 健身房目前：{count}/{capacity} 人")

            if count < THRESHOLD and not notified_low:
                # 剛剛降到門檻以下 → 發通知
                send_telegram(
                    f"🟢 <b>現在可以去健身房了！</b>\n\n"
                    f"🕐 時間：{now}\n"
                    f"👥 目前人數：<b>{count} 人</b>（容留 {capacity} 人）\n\n"
                    f"現在很空，快去 💪"
                )
                notified_low = True

            elif count >= THRESHOLD and notified_low:
                # 人數回升到門檻以上 → 解除通知
                send_telegram(
                    f"🔴 <b>健身房人數回升</b>\n\n"
                    f"🕐 時間：{now}\n"
                    f"👥 目前人數：<b>{count} 人</b>（已超過 {THRESHOLD} 人）"
                )
                notified_low = False

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
