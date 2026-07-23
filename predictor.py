import time
import math
import json
import urllib.request
import urllib.error
from collections import deque, Counter
from database import load_recent_history, save_round

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?ts={}"

# ---------- HTTP ফাংশন (requests ছাড়া) ----------
def http_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except:
        return None

def http_post(url, json_data):
    try:
        data = json.dumps(json_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except:
        return None

# ---------- Predictor ক্লাস ----------
class Predictor:
    def __init__(self):
        self.history = deque(maxlen=300)
        self.wins, self.losses, self.streak, self.best_streak, self.total_predictions = 0, 0, 0, 0, 0
        self.running, self.chat_id = False, None
        self.load_from_db()

    def load_from_db(self):
        for _, num, _, _, _, _ in load_recent_history():
            if num is not None:
                self.history.append(num)

    def update(self, num, period, prediction=None, result=None, range_pred=None):
        size = "BIG" if num >= 5 else "SMALL"
        self.history.append(num)
        save_round(period, num, size, prediction, result, range_pred)

    def fetch_data(self):
        try:
            ts = int(time.time() * 1000)
            data = http_get(API_URL.format(ts))
            if data:
                return data.get("data", {}).get("list", [])
        except:
            pass
        return []

    # ---------- Indicators ----------
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

    # ---------- PREDICT (আগের মতোই) ----------
    def predict_size(self):
        hist = list(self.history)
        if len(hist) < 20:
            return "BIG", 60, "5 • 9", "BULLISH", 50, "LOW", "NEUTRAL", "STABLE", 50, 50

        last = hist[-1]
        last_size = "BIG" if last >= 5 else "SMALL"

        specials = {0: ("BIG", 99, "0 • 2"), 4: ("BIG", 99, "3 • 5"), 5: ("SMALL", 99, "5 • 7"), 9: ("SMALL", 99, "7 • 9")}
        if last in specials:
            s = specials[last]
            return s[0], s[1], s[2], "BULLISH", 70, "LOW", "SPECIAL", "STABLE", 90, 10

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
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "STRONG BULLISH", 72, "LOW", "DRAGON", "STABLE", 95, 5

        if streak == 4:
            pred = last_size
            conf = 97
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "BULLISH", 68, "LOW", "4-STREAK", "STABLE", 90, 10

        if streak == 3:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 90
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "BEARISH", 55, "MEDIUM", "3-STREAK BREAK", "UNSTABLE", 75, 25

        if streak == 2:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 85
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "NEUTRAL", 52, "MEDIUM", "2-STREAK BREAK", "STABLE", 70, 30

        def is_alt(l):
            if len(hist) < l:
                return False
            for i in range(1, l):
                if (hist[-i] >= 5) == (hist[-i-1] >= 5):
                    return False
            return True

        if is_alt(8):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 92
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "BULLISH", 65, "LOW", "ALTERNATING 8", "STABLE", 85, 15

        if is_alt(6):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 88
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "BULLISH", 60, "LOW", "ALTERNATING 6", "STABLE", 80, 20

        if is_alt(5):
            pred = last_size
            conf = 85
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = f"{top[0][0]} • {top[1][0]}"
            else:
                rng = "5 • 9" if pred == "BIG" else "0 • 4"
            return pred, conf, rng, "NEUTRAL", 55, "MEDIUM", "TRAP", "STABLE", 72, 28

        ma5 = self.ma(hist, 5)
        ma10 = self.ma(hist, 10)
        ma20 = self.ma(hist, 20)
        ma_trend = "BULLISH" if ma5 > ma10 and ma10 > ma20 else "BEARISH" if ma5 < ma10 and ma10 < ma20 else "NEUTRAL"

        rsi_val = self.rsi(hist, 14)
        rsi_trend = "BULLISH" if rsi_val < 30 else "BEARISH" if rsi_val > 70 else "NEUTRAL"

        recent_30 = hist[-30:] if len(hist) >= 30 else hist
        big_c = sum(1 for x in recent_30 if x >= 5)
        small_c = len(recent_30) - big_c

        std = self.std_dev(hist, 20)
        std_text = "LOW" if std < 1.5 else "MEDIUM" if std < 2.5 else "HIGH"

        votes = {"BIG": 0, "SMALL": 0}
        votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        if ma_trend == "BULLISH":
            votes["BIG"] += 3
        elif ma_trend == "BEARISH":
            votes["SMALL"] += 3

        if rsi_trend == "BULLISH":
            votes["BIG"] += 2
        elif rsi_trend == "BEARISH":
            votes["SMALL"] += 2

        if big_c > small_c + 3:
            votes["SMALL"] += 2
        elif small_c > big_c + 3:
            votes["BIG"] += 2

        pred = max(votes, key=votes.get)
        total = sum(votes.values())
        diff = votes[pred] - (total - votes[pred])

        if diff >= 4:
            conf = 92
        elif diff >= 2:
            conf = 85
        else:
            conf = 70

        big_pct = int((votes["BIG"] / total) * 100) if total > 0 else 50
        small_pct = int((votes["SMALL"] / total) * 100) if total > 0 else 50
        ma_text = ma_trend
        pattern_text = "ALTERNATING" if is_alt(4) else "RANDOM"
        cycle_text = "STABLE" if std < 1.5 else "UNSTABLE"

        recent = hist[-20:] if len(hist) >= 20 else hist
        if pred == "BIG":
            nums = [x for x in recent if x >= 5]
        else:
            nums = [x for x in recent if x < 5]

        if len(nums) >= 2:
            cnt = Counter(nums)
            top = cnt.most_common(2)
            rng = f"{top[0][0]} • {top[1][0]}"
        else:
            rng = "5 • 9" if pred == "BIG" else "0 • 4"

        return pred, conf, rng, ma_text, rsi_val, std_text, pattern_text, cycle_text, big_pct, small_pct

    def get_next_prediction(self):
        size, conf, rng, ma, rsi, std, pattern, cycle, big_pct, small_pct = self.predict_size()
        return {
            "size": size,
            "confidence": conf,
            "range": rng,
            "ma": ma,
            "rsi": rsi,
            "std": std,
            "pattern": pattern,
            "cycle": cycle,
            "big_pct": big_pct,
            "small_pct": small_pct
        }

    def update_result(self, won):
        if won:
            self.wins += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.losses += 1
            self.streak = 0
        self.total_predictions += 1

    def send_message(self, text, chat_id=None):
        if chat_id is None:
            chat_id = self.chat_id
        if chat_id:
            try:
                from bot import TELEGRAM_API  # এখানে ইমপোর্ট করব
                http_post(TELEGRAM_API + "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
            except:
                pass

    def start(self, chat_id):
        if self.running:
            return
        self.running, self.chat_id = True, chat_id
        self.send_message("✅ প্রেডিকশন শুরু! (শুধু LEVEL 1-2: ≥85%)")
        import threading
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.send_message("⏹ বন্ধ করা হয়েছে।")

    # ========== LOOP ==========
    def _loop(self):
        seen = set()
        predictions_sent = set()
        current_prediction = None

        while self.running:
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

                    next_period = str(int(period) + 1)
                    pred_data = self.get_next_prediction()
                    
                    if pred_data["confidence"] >= 85:
                        current_prediction = {
                            "period": next_period,
                            "size": pred_data["size"],
                            "range": pred_data["range"]
                        }
                        from ui import format_prediction_ui
                        self.send_message(format_prediction_ui(pred_data, next_period))
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
                    from ui import format_result_ui
                    self.send_message(format_result_ui(period, number, actual_size, res, 
                                                       current_prediction["size"], 
                                                       current_prediction["range"]))
                    current_prediction = None

                time.sleep(1)
            except Exception as e:
                print("Loop error:", e)
                time.sleep(2)