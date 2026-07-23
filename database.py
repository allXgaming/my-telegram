import csv
import os
from datetime import datetime
from collections import Counter

CSV_FILE = "wingo_30s_data.csv"

def init_csv():
    """CSV ফাইল তৈরি করবে (যদি না থাকে) হেডারসহ"""
    if os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Period", "Number", "Size", "Prediction", "Result", "Range_Pred"])

def save_round(period, number, size, prediction, result, range_pred):
    """প্রতি রাউন্ড CSV-তে যোগ করবে"""
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([period, number, size, prediction, result, range_pred])

def load_all_history():
    """সমস্ত রেকর্ড লোড করবে (period, number, size, prediction, result, range_pred)"""
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    # হেডার বাদ
    data = []
    for row in rows[1:]:
        if len(row) < 6:
            row = row + [None] * (6 - len(row))
        # number কে integer করব
        try:
            num = int(row[1]) if row[1] else None
        except:
            num = None
        data.append((row[0], num, row[2], row[3], row[4], row[5]))
    return data

def load_recent_history(limit=None):
    """সব ডেটা রিটার্ন করবে (limit ইগনোর)"""
    return load_all_history()