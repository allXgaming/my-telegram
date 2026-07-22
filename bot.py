import time
import sqlite3
import threading
import math
import json
import requests
from collections import deque, Counter
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# ============ FIREBASE INIT ============
cred = credentials.Certificate("your-firebase-key.json")
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
BOT_TOKEN = "7768747736:AAHRFAiemrbWwo2aCY0geWyBBY385gPJcZ8"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

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
    if result == "WIN":
        status = "WIN"
    else:
        status = "LOSS"
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
        self.running = False
        self.chat_id = None
        self.allowed_users = set()
        self.load_from_db()
        self.start_user_listener()

    def load_from_db(self):
        for _, num, _, _, _, _ in load_recent_history(300):
            if num is not None:
                self.history.append(num)

    def start_user_listener(self):
        def listener_thread():
            try:
                query = fb_db.collection('users')
                def on_snapshot(doc_snapshot, changes, read_time):
                    updated_users = set()
                    for doc in doc_snapshot:
                        updated_users.add(doc.id)
                    self.allowed_users = updated_users
                
                query.on_snapshot(on_snapshot)
            except Exception as e:
                print("Listener error:", e)
                time.sleep(5)
        
        threading.Thread(target=listener_thread, daemon=True).start()

    def update(self, num, period, prediction=None, result=None, range_pred=None):
        size = "BIG" if num >= 5 else "SMALL"
        self.history.append(num)
        save_round(period, num, size, prediction, result, range_pred)

    def fetch_data(self):
        try:
            ts = int(time.time() * 1000)
            r = requests.get(API_URL.format(ts), timeout=10)
            if r.status_code == 200:
                return r.json().get("data", {}).get("list", [])
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
                requests.post(TELEGRAM_API + "sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
            except:
                pass

    def start(self, chat_id):
        if self.running:
            return
        self.running = True
        self.chat_id = chat_id
        self.send_message(chat_id, "Prediction started. Level 1 only (>=90%)")
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.chat_id:
            self.send_message(self.chat_id, "Stopped.")

    def _loop(self):
        seen = set()
        predictions_sent = set()
        current_prediction = None

        while self.running:
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
                            for cid in list(self.allowed_users):
                                self.send_message(cid, format_prediction_ui(pred_data, next_period))
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
                    
                    for cid in list(self.allowed_users):
                        self.send_message(cid, format_result_ui(period, number, actual_size, res, 
                                                           current_prediction["size"], 
                                                           current_prediction["range"]))
                    
                    # Update stats in Firebase
                    try:
                        fb_db.collection('stats').document('live_stats').set({
                            'wins': self.wins,
                            'losses': self.losses,
                            'streak': self.streak,
                            'best_streak': self.best_streak,
                            'total': self.total_predictions,
                            'last_updated': firestore.SERVER_TIMESTAMP
                        }, merge=True)
                    except:
                        pass
                    
                    current_prediction = None

                time.sleep(1)
            except Exception as e:
                print("Loop error:", e)
                time.sleep(2)

# ============ TELEGRAM HANDLER ============
predictor = Predictor()
last_update_id = 0

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

def main():
    global last_update_id
    print("Bot starting... (v2.0 - Firebase Real-time)")
    print("Only Level 1 (>=90%)")

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
                                [{"text": "START", "callback_data": "start"}],
                                [{"text": "STOP", "callback_data": "stop"}],
                                [{"text": "STATUS", "callback_data": "status"}],
                                [{"text": "CONTACT", "url": "https://t.me/your_username"}]
                            ]
                        }
                        requests.post(TELEGRAM_API + "sendMessage", json={
                            "chat_id": chat_id,
                            "text": "SUBHA Bot v2.0\n\nReal-time prediction bot.\nOnly Level 1 (>=90%)",
                            "reply_markup": keyboard
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
                            predictor.send_message(chat_id, "Already running")
                    elif data == "stop":
                        predictor.stop()
                    elif data == "status":
                        stats = f"STATS\nWin: {predictor.wins}\nLoss: {predictor.losses}\nStreak: {predictor.streak}\nBest: {predictor.best_streak}\nTotal: {predictor.total_predictions}"
                        predictor.send_message(chat_id, stats)
            time.sleep(1)
        except Exception as e:
            print("Main error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()