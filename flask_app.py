import os
import re
import requests
import telebot
from telebot import types
from flask import Flask, request

TOKEN = "8966729910:AAECEcUt0JREMxTYKDzH1wk65A2Ffj6324o"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

user_lang = {}

TEXT = {
    "ar": {
        "welcome": "أهلاً بك! اختر من القائمة:",
        "menu_convert": "💱 تحويل العملات",
        "menu_calc": "🧮 حاسبة سريعة",
        "menu_rates": "📊 أسعار اليوم",
        "menu_lang": "🌐 تغيير اللغة",
        "convert_help": "أرسل مثلاً: 100 USD MAD",
        "calc_help": "أرسل عملية حسابية مثلاً: 50 * 12",
        "rate_result": "💱 1 {frm} = {rate} {to}\nالنتيجة: {amount} {frm} = {result} {to}",
        "error": "⚠️ حدث خطأ، تأكد من الصيغة.",
        "rates_title": "📊 أسعار اليوم مقابل الدرهم المغربي:",
    },
    "en": {
        "welcome": "Welcome! Choose from the menu:",
        "menu_convert": "💱 Currency Converter",
        "menu_calc": "🧮 Quick Calculator",
        "menu_rates": "📊 Today's Rates",
        "menu_lang": "🌐 Change Language",
        "convert_help": "Send e.g.: 100 USD MAD",
        "calc_help": "Send a calculation e.g.: 50 * 12",
        "rate_result": "💱 1 {frm} = {rate} {to}\nResult: {amount} {frm} = {result} {to}",
        "error": "⚠️ Error, check the format.",
        "rates_title": "📊 Today's rates vs Moroccan Dirham:",
    },
}


def lang_of(chat_id):
    return user_lang.get(chat_id, "ar")


def main_menu(chat_id):
    t = TEXT[lang_of(chat_id)]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(t["menu_convert"], t["menu_calc"])
    kb.row(t["menu_rates"], t["menu_lang"])
    return kb


def lang_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🇲🇦 العربية", callback_data="setlang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"),
    )
    return kb


@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    if chat_id not in user_lang:
        bot.send_message(chat_id, "اختر لغتك / Choose language:", reply_markup=lang_keyboard())
    else:
        t = TEXT[lang_of(chat_id)]
        bot.send_message(chat_id, t["welcome"], reply_markup=main_menu(chat_id))


@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang_"))
def set_lang(call):
    chat_id = call.message.chat.id
    lang = call.data.split("_")[1]
    user_lang[chat_id] = lang
    t = TEXT[lang]
    bot.send_message(chat_id, t["welcome"], reply_markup=main_menu(chat_id))


@bot.message_handler(func=lambda m: m.text in [TEXT["ar"]["menu_lang"], TEXT["en"]["menu_lang"]])
def change_lang(message):
    bot.send_message(message.chat.id, "اختر لغتك / Choose language:", reply_markup=lang_keyboard())


@bot.message_handler(func=lambda m: m.text in [TEXT["ar"]["menu_convert"], TEXT["en"]["menu_convert"]])
def ask_convert(message):
    t = TEXT[lang_of(message.chat.id)]
    bot.send_message(message.chat.id, t["convert_help"])


@bot.message_handler(func=lambda m: m.text in [TEXT["ar"]["menu_calc"], TEXT["en"]["menu_calc"]])
def ask_calc(message):
    t = TEXT[lang_of(message.chat.id)]
    bot.send_message(message.chat.id, t["calc_help"])


@bot.message_handler(func=lambda m: m.text in [TEXT["ar"]["menu_rates"], TEXT["en"]["menu_rates"]])
def today_rates(message):
    chat_id = message.chat.id
    t = TEXT[lang_of(chat_id)]
    try:
        data = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        rates = data["rates"]
        msg = f"{t['rates_title']}\n"
        msg += f"1 USD = {rates['MAD']:.2f} MAD\n"
        msg += f"1 EUR = {rates['MAD']/rates['EUR']:.2f} MAD\n"
        msg += f"1 USD = {rates['EUR']:.4f} EUR"
        bot.send_message(chat_id, msg)
    except Exception:
        bot.send_message(chat_id, t["error"])


CONVERT_RE = re.compile(r"^\s*([\d.]+)\s*([A-Za-z]{3})\s*([A-Za-z]{3})\s*$")
CALC_RE = re.compile(r"^[\d\.\+\-\*\/\(\)\s]+$")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    chat_id = message.chat.id
    t = TEXT[lang_of(chat_id)]
    text = message.text.strip()

    m = CONVERT_RE.match(text)
    if m:
        amount, frm, to = float(m.group(1)), m.group(2).upper(), m.group(3).upper()
        try:
            data = requests.get(f"https://open.er-api.com/v6/latest/{frm}", timeout=10).json()
            rate = data["rates"][to]
            result = round(amount * rate, 2)
            bot.send_message(chat_id, t["rate_result"].format(
                frm=frm, to=to, rate=round(rate, 4), amount=amount, result=result))
        except Exception:
            bot.send_message(chat_id, t["error"])
        return

    if CALC_RE.match(text) and any(ch.isdigit() for ch in text):
        try:
            result = eval(text, {"__builtins__": {}}, {})
            bot.send_message(chat_id, str(result))
        except Exception:
            bot.send_message(chat_id, t["error"])
        return

    bot.send_message(chat_id, t["welcome"], reply_markup=main_menu(chat_id))


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"https://telegram-bot-xxxx.onrender.com/{TOKEN}")
    return "Webhook set!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
