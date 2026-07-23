import time
import threading
import requests
from database import init_excel
from predictor import Predictor
from ui import format_prediction_ui, format_result_ui

# ============ কনফিগারেশন ============
BOT_TOKEN = "7768747736:AAHRFAiemrbWwo2aCY0geWyBBY385gPJcZ8"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# ============ গ্লোবাল ভেরিয়েবল ============
predictor = Predictor()
last_update_id = 0

# ============ টেলিগ্রাম ফাংশন ============
def get_updates(offset=None):
    url = TELEGRAM_API + "getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []

def send_message(chat_id, text, parse_mode="HTML"):
    try:
        requests.post(TELEGRAM_API + "sendMessage", 
                     json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode}, 
                     timeout=10)
    except:
        pass

# ============ মেইন ফাংশন ============
def main():
    global last_update_id
    print("🤖 বট চালু হচ্ছে... (Excel ডেটাবেস + মডুলার)")
    print("📊 LEVEL 1 (≥92%) | LEVEL 2 (≥85%)")
    
    # Excel ফাইল চেক/ক্রিয়েট
    init_excel()

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message")
                if msg:
                    chat_id = msg["chat"]["id"]
                    if msg.get("text") == "/start":
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "▶️ START", "callback_data": "start"}],
                                [{"text": "⏹ STOP", "callback_data": "stop"}],
                                [{"text": "📊 STATUS", "callback_data": "status"}],
                                [{"text": "📞 CONTACT", "url": "https://t.me/your_username"}]
                            ]
                        }
                        requests.post(TELEGRAM_API + "sendMessage", json={
                            "chat_id": chat_id,
                            "text": "🤖 *SUBHA v17.0 (NO SKIP + NEW UI)*\n\n✅ প্রতি পিরিয়ডে প্রেডিকশন (স্কিপিং বন্ধ)\n✅ LEVEL 1 (≥92%) | LEVEL 2 (≥85%)\n✅ নতুন UI - AI ANALYSIS + VOTING + METRICS\n\nনিচের বোতাম চাপুন।",
                            "reply_markup": keyboard,
                            "parse_mode": "Markdown"
                        }, timeout=10)

                cb = update.get("callback_query")
                if cb:
                    chat_id = cb["message"]["chat"]["id"]
                    data = cb["data"]
                    cb_id = cb["id"]
                    requests.post(TELEGRAM_API + "answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)

                    if data == "start":
                        if not predictor.running:
                            predictor.start(chat_id)
                        else:
                            send_message(chat_id, "⏳ চলছে...")
                    elif data == "stop":
                        predictor.stop()
                    elif data == "status":
                        stats = (f"📊 *পরিসংখ্যান*\n✅ জয়: {predictor.wins}\n❌ হার: {predictor.losses}\n"
                                 f"🔥 স্ট্রিক: {predictor.streak}\n🏆 সেরা: {predictor.best_streak}\n📈 মোট: {predictor.total_predictions}")
                        send_message(chat_id, stats, parse_mode="Markdown")
            time.sleep(1)
        except Exception as e:
            print("Main error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()