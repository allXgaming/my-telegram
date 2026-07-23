import time
import json
import urllib.request
import urllib.error
from database import init_csv
from predictor import Predictor

# ============ কনফিগারেশন ============
BOT_TOKEN = "7768747736:AAHRFAiemrbWwo2aCY0geWyBBY385gPJcZ8"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# ============ HTTP ফাংশন ============
def http_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print("HTTP GET error:", e)
        return None

def http_post(url, json_data):
    try:
        data = json.dumps(json_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print("HTTP POST error:", e)
        return None

# ============ টেলিগ্রাম ফাংশন ============
def get_updates(offset=None):
    url = TELEGRAM_API + "getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query}"
        data = http_get(full_url)
        if data:
            return data.get("result", [])
    except Exception as e:
        print("get_updates error:", e)
    return []

def send_message(chat_id, text, parse_mode="HTML"):
    try:
        http_post(TELEGRAM_API + "sendMessage", 
                 {"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
    except Exception as e:
        print("send_message error:", e)

# ============ গ্লোবাল ভেরিয়েবল ============
predictor = Predictor()
last_update_id = 0

# ============ মেইন ফাংশন ============
def main():
    global last_update_id
    print("🤖 বট চালু হচ্ছে... (বিল্ট-ইন মডিউল + CSV)")
    print("📊 LEVEL 1 (≥92%) | LEVEL 2 (≥85%)")
    
    # CSV ফাইল তৈরি (যদি না থাকে)
    init_csv()

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                
                # ---------- মেসেজ হ্যান্ডলিং ----------
                msg = update.get("message")
                if msg:
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text")
                    
                    if text == "/start":
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "▶️ START", "callback_data": "start"}],
                                [{"text": "⏹ STOP", "callback_data": "stop"}],
                                [{"text": "📊 STATUS", "callback_data": "status"}],
                                [{"text": "📞 CONTACT", "url": "https://t.me/your_username"}]
                            ]
                        }
                        http_post(TELEGRAM_API + "sendMessage", json={
                            "chat_id": chat_id,
                            "text": "🤖 *SUBHA v17.0 (NO SKIP + NEW UI)*\n\n✅ প্রতি পিরিয়ডে প্রেডিকশন (স্কিপিং বন্ধ)\n✅ LEVEL 1 (≥92%) | LEVEL 2 (≥85%)\n✅ নতুন UI - AI ANALYSIS + VOTING + METRICS\n\nনিচের বোতাম চাপুন।",
                            "reply_markup": keyboard,
                            "parse_mode": "Markdown"
                        })
                    
                    elif text == "/predictor":
                        send_message(chat_id, "হ্যালো 👋")
                
                # ---------- ক্যালব্যাক কোয়েরি হ্যান্ডলিং ----------
                cb = update.get("callback_query")
                if cb:
                    chat_id = cb["message"]["chat"]["id"]
                    data = cb["data"]
                    cb_id = cb["id"]
                    http_post(TELEGRAM_API + "answerCallbackQuery", {"callback_query_id": cb_id})

                    if data == "start":
                        if not predictor.running:
                            predictor.start(chat_id)
                        else:
                            send_message(chat_id, "⏳ বট ইতিমধ্যেই চলছে...")
                    elif data == "stop":
                        predictor.stop()
                    elif data == "status":
                        stats = (f"📊 *পরিসংখ্যান*\n✅ জয়: {predictor.wins}\n❌ হার: {predictor.losses}\n"
                                 f"🔥 স্ট্রিক: {predictor.streak}\n🏆 সেরা: {predictor.best_streak}\n📈 মোট: {predictor.total_predictions}")
                        send_message(chat_id, stats, parse_mode="Markdown")
            
            time.sleep(1)
        except Exception as e:
            print("Main loop error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()