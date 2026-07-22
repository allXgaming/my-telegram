import telebot
from telebot import types
import json

API_KEY = '7616902302:AAEp4VjUFX9mfBqYuc_ZY7pfuntVvQ8dpWE'  # এখানে BotFather থেকে পাওয়া টোকেন বসাও
bot = telebot.TeleBot(API_KEY)

def load_games():
    with open('games.json', 'r') as f:
        return json.load(f)

@bot.message_handler(commands=['start'])
def welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎮 Go to Gaming Hub", url="https://allxgaming.vercel.app/"))
    bot.send_message(
        message.chat.id,
        "👋 Welcome to AllXGaming Bot!\n\n"
        "🎯 Just type a game name like `ludo`, `car game`, `snake`\n"
        "Or tap below to visit full game hub 👇",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: True)
def find_game(message):
    text = message.text.strip().lower()
    games = load_games()

    if text in games:
        url = games[text]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("▶️ Play Now", url=url))
        bot.send_message(message.chat.id, f"🎯 Found: *{text.title()}*", reply_markup=markup, parse_mode='Markdown')
        return

    for name, url in games.items():
        if text in name:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("▶️ Play Now", url=url))
            bot.send_message(message.chat.id, f"🎯 Closest match: *{name.title()}*", reply_markup=markup, parse_mode='Markdown')
            return

    bot.send_message(message.chat.id, "🤖 Sorry, I didn’t find that game. Try something like `ludo`, `snake`, etc.")

bot.infinity_polling()
