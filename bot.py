import time
import sqlite3
import threading
import math
import json
import urllib.request
import urllib.error
from collections import deque, Counter
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# ============ FIREBASE INIT ============
cred = credentials.Certificate("your-firebase-key.json")  # আপনার JSON ফাইলের নাম দিন
firebase_admin.initialize_app(cred)
fb_db = firestore.client()

# ============ DATABASE ============
def init_db():
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rounds
                 (period TEXT PRIMARY KEY, number INTEGER, size TEXT,
                  prediction TEXT, result TEXT, range_pred TEXT)''')
    try:
        c.execute("ALTER TABLE rounds ADD COLUMN range_pred TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def save_round(period, number, size, prediction, result, range_pred):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO rounds (period, number, size, prediction, result, range_pred)
                 VALUES (?, ?, ?, ?, ?, ?)''', (period, number, size, prediction, result, range_pred))
    conn.commit()
    conn.close()

def load_recent_history(limit=300):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    try:
        c.execute('''SELECT period, number, size, prediction, result, range_pred FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
    except sqlite3.OperationalError:
        c.execute('''SELECT period, number, size, prediction, result FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = [(r[0], r[1], r[2], r[3], r[4], None) for r in c.fetchall()]
    conn.close()
    return rows

init_db()

# ============ CONSTANTS ============
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?ts={}"
BOT_TOKEN = "7768747736:AAHRFAiemrbWwo2aCY0geWyBBY385gPJcZ8"  # আপনার টোকেন
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# ============ HELPER: urllib.request based HTTP ============
def http_get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception:
        return None

def http_post(url, data=None, json_data=None, timeout=10):
    try:
        headers = {'Content-Type': 'application/json'} if json_data else {}
        if json_data:
            data = json.dumps(json_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception:
        return None

# ============ UI FORMAT ============
def format_prediction_ui(pred_data, period):
    size = pred_data["size"]
    conf = pred_data["confidence"]
    num_range = pred_data["range"]
    filled = int(16 * conf / 100)
    bar = "=" * filled + "-" * (16 - filled)
    
    if conf >= 90:
        trend = "STRONG"
    elif conf >= 80:
        trend = "MODERATE"
    else:
        trend = "WEAK"
    
    ui = f"""
╭────────────────────────────╮
│        SUBHA MODS           │
│      AI PREDICTION          │
├────────────────────────────┤
│ PERIOD                      │
│ {period}                    │
├────────────────────────────┤
│ SIGNAL          {size:^8}   │
│ RANGE           {num_range:^8} │
│ SCORE           {conf:.1f}%  │
│ {bar}                       │
├────────────────────────────┤
│ TREND           {trend:^10} │
╰────────────────────────────╯
"""
    return ui

def format_result_ui(period, number, actual_size, result, pred, range_pred):
    status = "WIN" if result == "WIN" else "LOSS"
    ui = f"""
{status}
╭────────────────────────────╮
│        RESULT               │
├────────────────────────────┤
│ PERIOD      {period}        │
│ PREDICT     {pred}          │
│ ACTUAL      {actual_size} [{number}] │
│ RANGE       {range_pred}    │
╰────────────────────────────╯
"""
    return ui

# ============ PREDICTOR ============
class Predictor:
    def __init__(self):
        self.history = deque(maxlen=300)
        self.wins = 0
        self.losses = 0
        self.streak = 0
        self.best_streak = 0
        self.total_predictions = 0
        self.running = False          # Firebase settings থেকে আপডেট হবে
        self.allowed_users = set()    # Firebase users collection থেকে আপডেট হবে
        self.active_chats = set()     # যারা টেলিগ্রামে START চেপেছে
        self.load_from_db()
        self.start_user_listener()
        self.start_settings_listener()

    def load_from_db(self):
        for _, num, _, _, _, _ in load_recent_history(300):
            if num is not None:
                self.history.append(num)

    # ---------- Firebase Listeners ----------
    def start_user_listener(self):
        """users collection এর পরিবর্তন শুনে allowed_users আপডেট করে"""
        def listener_thread():
            try:
                query = fb_db.collection('users')
                def on_snapshot(doc_snapshot, changes, read_time):
                    updated_users = set()
                    for doc in doc_snapshot:
                        updated_users.add(doc.id)   # doc.id = chat_id
                    self.allowed_users = updated_users
                    print(f"Allowed users updated: {len(self.allowed_users)} users")
                
                query.on_snapshot(on_snapshot)
            except Exception as e:
                print("User listener error:", e)
                time.sleep(5)
        
        threading.Thread(target=listener_thread, daemon=True).start()

    def start_settings_listener(self):
        """settings/bot_config ডকুমেন্টের পরিবর্তন শুনে running flag আপডেট করে"""
        def listener_thread():
            try:
                doc_ref = fb_db.collection('settings').document('bot_config')
                def on_snapshot(doc_snapshot, changes, read_time):
                    if doc_snapshot:
                        data = doc_snapshot[0].to_dict() if doc_snapshot else {}
                        is_running = data.get('is_running', False)
                        self.running = is_running
                        print(f"Bot running state: {self.running}")
                
                doc_ref.on_snapshot(on_snapshot)
            except Exception as e:
                print("Settings listener error:", e)
                time.sleep(5)
        
        threading.Thread(target=listener_thread, daemon=True).start()

    # ---------- Core Methods ----------
    def update(self, num, period, prediction=None, result=None, range_pred=None):
        size = "BIG" if num >= 5 else "SMALL"
        self.history.append(num)
        save_round(period, num, size, prediction, result, range_pred)

    def fetch_data(self):
        try:
            ts = int(time.time() * 1000)
            url = API_URL.format(ts)
            resp = http_get(url, timeout=10)
            if resp:
                data = json.loads(resp)
                return data.get("data", {}).get("list", [])
        except:
            pass
        return []

    def ma(self, data, w):
        return sum(data[-w:]) / w if len(data) >= w else sum(data) / len(data) if data else 0

    def rsi(self, data, w=14):
        if len(data) < w + 1:
            return 50
        g, l = 0, 0
        for i in range(1, w + 1):
            d = data[-i] - data[-i-1]
            g += d if d > 0 else 0
            l += abs(d) if d < 0 else 0
        return 100 - (100 / (1 + (g / l))) if l != 0 else 100

    def std_dev(self, data, w=20):
        if len(data) < w:
            return 0
        recent = data[-w:]
        mean = sum(recent) / w
        return math.sqrt(sum((x - mean) ** 2 for x in recent) / w)

    def predict_size(self):
        hist = list(self.history)
        if len(hist) < 20:
            return "BIG", 60, "5-9"

        last = hist[-1]
        last_size = "BIG" if last >= 5 else "SMALL"

        specials = {0: ("BIG", 99, "0-2"), 4: ("BIG", 97, "3-5"), 5: ("SMALL", 97, "5-7"), 9: ("SMALL", 99, "7-9")}
        if last in specials:
            return specials[last]

        streak = 1
        for i in range(len(hist)-2, -1, -1):
            if (hist[i] >= 5) == (last >= 5):
                streak += 1
            else:
                break

        if streak >= 5:
            pred = last_size
            conf = 99
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]}-{top[1][0]}"
            else:
                rng = "5-9" if pred == "BIG" else "0-4"
            return pred, conf, rng

        if streak == 4:
            pred = last_size
            conf = 97
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]}-{top[1][0]}"
            else:
                rng = "5-9" if pred == "BIG" else "0-4"
            return pred, conf, rng

        ma5 = self.ma(hist, 5)
        ma10 = self.ma(hist, 10)
        ma20 = self.ma(hist, 20)
        ma_trend = "BIG" if ma5 > ma10 and ma10 > ma20 else "SMALL" if ma5 < ma10 and ma10 < ma20 else "NEUTRAL"

        rsi_val = self.rsi(hist, 14)
        rsi_trend = "BIG" if rsi_val < 30 else "SMALL" if rsi_val > 70 else "NEUTRAL"

        recent_30 = hist[-30:] if len(hist) >= 30 else hist
        big_c = sum(1 for x in recent_30 if x >= 5)
        small_c = len(recent_30) - big_c
        freq_trend = "BIG" if big_c > small_c + 3 else "SMALL" if small_c > big_c + 3 else "NEUTRAL"

        vol = self.std_dev(hist, 20)
        vol_factor = 1.0 if vol < 1.5 else 0.8 if vol < 2.5 else 0.5

        def is_alt(l):
            if len(hist) < l:
                return False
            for i in range(1, l):
                if (hist[-i] >= 5) == (hist[-i-1] >= 5):
                    return False
            return True

        votes = {"BIG": 0, "SMALL": 0}

        if streak == 3:
            votes["SMALL" if last_size == "BIG" else "BIG"] += 2
        elif streak == 2:
            votes["SMALL" if last_size == "BIG" else "BIG"] += 1
        else:
            votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        if is_alt(8):
            votes["SMALL" if last_size == "BIG" else "BIG"] += 4
        elif is_alt(6):
            votes["SMALL" if last_size == "BIG" else "BIG"] += 2
        elif is_alt(5):
            votes[last_size] += 3

        if ma_trend != "NEUTRAL":
            votes[ma_trend] += 5
        else:
            votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        if rsi_trend != "NEUTRAL":
            votes[rsi_trend] += 4

        if freq_trend != "NEUTRAL":
            votes[freq_trend] += 4
        else:
            votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        pred = max(votes, key=votes.get)
        total = sum(votes.values())
        diff = votes[pred] - (total - votes[pred])

        if total == 0:
            conf = 60
        else:
            base = 75 + min(20, int((diff / total) * 30))
            conf = int(base * vol_factor)

        if diff < 3 or conf < 90:
            conf = min(conf, 70)

        conf = min(99, max(50, conf))

        recent = hist[-20:] if len(hist) >= 20 else hist
        if pred == "BIG":
            nums = [x for x in recent if x >= 5]
        else:
            nums = [x for x in recent if x < 5]

        if len(nums) >= 2:
            cnt = Counter(nums)
            top = cnt.most_common(2)
            rng = f"{top[0][0]}-{top[1][0]}"
        else:
            rng = "5-9" if pred == "BIG" else "0-4"

        return pred, conf, rng

    def get_next_prediction(self):
        size, conf, rng = self.predict_size()
        return {"size": size, "confidence": conf, "range": rng}

    def update_result(self, won):
        if won:
            self.wins += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.losses += 1
            self.streak = 0
        self.total_predictions += 1

    def send_message(self, chat_id, text):
        if chat_id:
            try:
                url = TELEGRAM_API + "sendMessage"
                payload = {"chat_id": chat_id, "text": text}
                http_post(url, json_data=payload, timeout=10)
            except:
                pass

    def broadcast(self, text):
        """সব অনুমোদিত ও সক্রিয় ইউজারকে মেসেজ পাঠায়"""
        for cid in list(self.allowed_users.intersection(self.active_chats)):
            self.send_message(cid, text)

    # ---------- Telegram Commands ----------
    def start_chat(self, chat_id):
        """ইউজার START চাপলে তাকে active তালিকায় যোগ করি (যদি অনুমোদিত হয়)"""
        if str(chat_id) in self.allowed_users:
            self.active_chats.add(str(chat_id))
            self.send_message(chat_id, "You are now active. Predictions will be sent here.")
        else:
            self.send_message(chat_id, "You are not authorized to use this bot.")

    def stop_chat(self, chat_id):
        if str(chat_id) in self.active_chats:
            self.active_chats.remove(str(chat_id))
            self.send_message(chat_id, "You have stopped receiving predictions.")

    def status(self, chat_id):
        stats = (f"STATS\nWin: {self.wins}\nLoss: {self.losses}\n"
                 f"Streak: {self.streak}\nBest: {self.best_streak}\n"
                 f"Total: {self.total_predictions}")
        self.send_message(chat_id, stats)

    # ---------- Main Loop ----------
    def _loop(self):
        seen = set()
        predictions_sent = set()
        current_prediction = None

        while True:
            # শুধু চলমান অবস্থায় এবং অনুমোদিত ইউজার থাকলে কাজ করবে
            if not self.running:
                time.sleep(2)
                continue

            if not self.allowed_users:
                time.sleep(2)
                continue

            try:
                data = self.fetch_data()
                if not data:
                    time.sleep(1)
                    continue

                latest = data[0]
                period = latest.get("issueNumber", "")
                num_str = latest.get("number", "")
                try:
                    number = int(num_str)
                except:
                    number = None

                if not period or not period.isdigit():
                    time.sleep(1)
                    continue

                if period not in seen:
                    if number is not None:
                        self.update(number, period)
                    seen.add(period)

                    if period not in predictions_sent:
                        next_period = str(int(period) + 1)
                        pred_data = self.get_next_prediction()
                        if pred_data["confidence"] >= 90:
                            current_prediction = {
                                "period": next_period,
                                "size": pred_data["size"],
                                "range": pred_data["range"]
                            }
                            self.broadcast(format_prediction_ui(pred_data, next_period))
                            predictions_sent.add(next_period)

                if current_prediction and current_prediction["period"] == period and number is not None:
                    actual_size = "BIG" if number >= 5 else "SMALL"
                    won = (actual_size == current_prediction["size"])
                    res = "WIN" if won else "LOSS"
                    self.update_result(won)
                    self.update(number, period,
                               prediction=current_prediction["size"],
                               result=res,
                               range_pred=current_prediction["range"])

                    self.broadcast(format_result_ui(period, number, actual_size, res,
                                                    current_prediction["size"],
                                                    current_prediction["range"]))

                    # Firebase-এ স্ট্যাটস আপডেট
                    try:
                        fb_db.collection('stats').document('live_stats').set({
                            'wins': self.wins,
                            'losses': self.losses,
                            'streak': self.streak,
                            'best_streak': self.best_streak,
                            'total': self.total_predictions,
                            'last_updated': firestore.SERVER_TIMESTAMP
                        }, merge=True)
                    except Exception as e:
                        print("Stats update error:", e)

                    current_prediction = None

                time.sleep(1)
            except Exception as e:
                print("Loop error:", e)
                time.sleep(2)

# ============ TELEGRAM HANDLER ============
predictor = Predictor()
last_update_id = 0

# বটের লুপটি একটি থ্রেডে চালু করি
threading.Thread(target=predictor._loop, daemon=True).start()

def get_updates(offset=None):
    url = TELEGRAM_API + "getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{url}?{query}"
    try:
        resp = http_get(full_url, timeout=35)
        if resp:
            data = json.loads(resp)
            return data.get("result", [])
    except:
        pass
    return []

def main():
    global last_update_id
    print("Bot starting with Firebase user control...")
    print("Only authorized users (in Firestore 'users' collection) can receive predictions.")

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message")
                if msg:
                    chat_id = str(msg["chat"]["id"])   # string হিসেবে রাখি
                    if msg.get("text") == "/start":
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "START", "callback_data": "start"}],
                                [{"text": "STOP", "callback_data": "stop"}],
                                [{"text": "STATUS", "callback_data": "status"}],
                                [{"text": "CONTACT", "url": "https://t.me/your_username"}]
                            ]
                        }
                        http_post(TELEGRAM_API + "sendMessage", json_data={
                            "chat_id": chat_id,
                            "text": "SUBHA Bot v2.0 (Firebase Auth)\n\nYou must be authorized to use this bot.",
                            "reply_markup": keyboard
                        }, timeout=10)

                cb = update.get("callback_query")
                if cb:
                    chat_id = str(cb["message"]["chat"]["id"])
                    data = cb["data"]
                    cb_id = cb["id"]
                    http_post(TELEGRAM_API + "answerCallbackQuery", json_data={"callback_query_id": cb_id}, timeout=5)

                    if data == "start":
                        predictor.start_chat(chat_id)
                    elif data == "stop":
                        predictor.stop_chat(chat_id)
                    elif data == "status":
                        predictor.status(chat_id)

            time.sleep(1)
        except Exception as e:
            print("Main error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()