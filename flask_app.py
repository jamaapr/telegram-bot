import os
import re
from datetime import datetime, timezone
import requests
import telebot
from telebot import types
from flask import Flask, request

TOKEN = "8966729910:AAECEcUt0JREMxTYKDzH1wk65A2Ffj6324o"
RENDER_URL = "https://telegram-bot-production-7d43.up.railway.app"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

MAIN_CURRENCIES = ["USD", "EUR", "GBP", "MAD", "SAR", "AED", "JPY", "CNY"]


def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💱 Currency Rates", callback_data="menu_rates"),
        types.InlineKeyboardButton("🧮 Calculator", callback_data="menu_calc"),
    )
    kb.add(types.InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"))
    return kb


def currency_menu():
    kb = types.InlineKeyboardMarkup(row_width=4)
    buttons = [
        types.InlineKeyboardButton(c, callback_data=f"rate_{c}")
        for c in MAIN_CURRENCIES
    ]
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu_main"))
    return kb


def back_to_rates_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💱 Choose Another Currency", callback_data="menu_rates"))
    kb.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main"))
    return kb


def build_rates_message(base):
    data = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10).json()
    rates = data["rates"]
    lines = [f"💱 <b>{base} Exchange Rates</b>", f"🕒 {now_str()}", ""]
    for c in MAIN_CURRENCIES:
        if c == base:
            continue
        lines.append(f"1 {base} = <b>{rates[c]:.4f}</b> {c}")
    return "\n".join(lines)


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Welcome!</b>\nChoose an option below:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_main(call):
    bot.edit_message_text(
        "👋 <b>Welcome!</b>\nChoose an option below:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "menu_rates")
def cb_rates_menu(call):
    bot.edit_message_text(
        "💱 <b>Select a base currency:</b>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=currency_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_"))
def cb_show_rate(call):
    base = call.data.split("_")[1]
    try:
        text = build_rates_message(base)
    except Exception:
        text = "⚠️ Could not fetch rates right now. Please try again."
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=back_to_rates_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "menu_calc")
def cb_calc(call):
    bot.edit_message_text(
        "🧮 <b>Calculator</b>\n\nSend me a calculation, e.g.:\n<code>50 * 12</code>\n<code>(100 + 250) / 2</code>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main")
        ),
    )


@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def cb_help(call):
    bot.edit_message_text(
        "ℹ️ <b>How to use this bot</b>\n\n"
        "💱 <b>Currency Rates</b> — tap a currency to instantly see live rates.\n"
        "🧮 <b>Calculator</b> — send any math expression directly.\n\n"
        "Rates are updated live each time you check them.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main")
        ),
    )


CALC_RE = re.compile(r"^[\d\.\+\-\*\/\(\)\s]+$")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    text = message.text.strip()
    if CALC_RE.match(text) and any(ch.isdigit() for ch in text):
        try:
            result = eval(text, {"__builtins__": {}}, {})
            bot.send_message(message.chat.id, f"🧮 <code>{text}</code> = <b>{result}</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(message.chat.id, "⚠️ Invalid expression.")
        return
    bot.send_message(
        message.chat.id,
        "👋 Choose an option below:",
        reply_markup=main_menu(),
    )


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
    return "Webhook set!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
