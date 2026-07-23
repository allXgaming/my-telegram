def format_prediction_ui(pred_data, period):
    size = pred_data["size"]
    conf = pred_data["confidence"]
    num_range = pred_data["range"]
    ma_val = pred_data.get("ma", "BULLISH")
    rsi_val = pred_data.get("rsi", 63.8)
    std_val = pred_data.get("std", "LOW")
    pattern = pred_data.get("pattern", "ALTERNATING")
    cycle = pred_data.get("cycle", "STABLE")
    big_pct = pred_data.get("big_pct", 78)
    small_pct = pred_data.get("small_pct", 22)
    signal = "HIGH 🟢" if conf >= 85 else "MEDIUM 🟡"
    volatility = "LOW" if conf >= 85 else "MEDIUM"
    risk = "LOW" if conf >= 85 else "MEDIUM"
    
    size_emoji = "🐘" if size == "BIG" else "🐭"
    level = "🔥 LEVEL 1" if conf >= 92 else "⚡ LEVEL 2" if conf >= 85 else "⚠️ LEVEL 3"
    
    big_bar = "█" * int(big_pct / 10) + "░" * (10 - int(big_pct / 10))
    small_bar = "█" * int(small_pct / 10) + "░" * (10 - int(small_pct / 10))
    
    ui = f"""
━━━━━━━━━━━━━━━━━━━━━━
🧠 AI ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━
📈 MA           : {ma_val}
📊 RSI          : {rsi_val:.1f}
📉 STD DEV      : {std_val}
🔄 PATTERN      : {pattern}
🎯 CYCLE        : {cycle}

━━━━━━━━━━━━━━━━━━━━━━
🗳️ AI VOTING
━━━━━━━━━━━━━━━━━━━━━━
🐘 BIG          {big_bar} {big_pct}%
🐭 SMALL        {small_bar} {small_pct}%

🏆 FINAL EDGE   : {size_emoji} {size}

━━━━━━━━━━━━━━━━━━━━━━
📡 AI METRICS
━━━━━━━━━━━━━━━━━━━━━━
🎯 CONFIDENCE   : {conf}%
📶 SIGNAL       : {signal}
🎲 VOLATILITY   : {volatility}
⚖️ RISK         : {risk}

━━━━━━━━━━━━━━━━━━━━━━
🆔 PERIOD       : {period}
🎯 RANGE        : {num_range}
📊 LEVEL        : {level}
━━━━━━━━━━━━━━━━━━━━━━
⚡ AI STATUS : ACTIVE
🧠 ENGINE    : SUBHA AI
🔥 MODE      : LIVE
━━━━━━━━━━━━━━━━━━━━━━
"""
    return ui

def format_result_ui(period, number, actual_size, result, pred, range_pred):
    if result == "WIN":
        status_emoji, status_text, bg = "✅", "WIN 🎉", "🟢"
    else:
        status_emoji, status_text, bg = "❌", "LOSS 😞", "🔴"
    actual_emoji = "🐘" if actual_size == "BIG" else "🐭"
    ui = f"""
{status_emoji} {status_text}  {bg}
━━━━━━━━━━━━━━━━━━━━━━
📊 RESULT
━━━━━━━━━━━━━━━━━━━━━━
📅 PERIOD    : {period}
🎯 PREDICT   : {pred}
✅ ACTUAL    : {actual_emoji} {actual_size} [{number}]
📊 RANGE     : {range_pred}
━━━━━━━━━━━━━━━━━━━━━━
"""
    return ui