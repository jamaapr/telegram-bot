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

FIAT_CURRENCIES = ["USD", "EUR", "GBP", "MAD", "SAR", "AED", "JPY", "CNY"]

CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "USDC": "usd-coin",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "TRX": "tron",
}


def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def remove_old_keyboard(chat_id):
    try:
        bot.send_message(chat_id, "🔄 Updating...", reply_markup=types.ReplyKeyboardRemove())
    except Exception:
        pass


def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💱 Fiat Currencies", callback_data="menu_fiat"),
        types.InlineKeyboardButton("🪙 Crypto Currencies", callback_data="menu_crypto"),
    )
    kb.add(
        types.InlineKeyboardButton("🧮 Calculator", callback_data="menu_calc"),
        types.InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"),
    )
    return kb


def fiat_menu():
    kb = types.InlineKeyboardMarkup(row_width=4)
    kb.add(*[types.InlineKeyboardButton(c, callback_data=f"fiat_{c}") for c in FIAT_CURRENCIES])
    kb.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main"))
    return kb


def crypto_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[types.InlineKeyboardButton(c, callback_data=f"crypto_{c}") for c in CRYPTO_IDS])
    kb.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main"))
    return kb


def back_button(target):
    kb = types.InlineKeyboardMarkup()
    label = "⬅️ Back to Fiat" if target == "fiat" else "⬅️ Back to Crypto"
    kb.add(types.InlineKeyboardButton(label, callback_data=f"menu_{target}"))
    kb.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"))
    return kb


def build_fiat_message(base):
    data = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10).json()
    rates = data["rates"]
    lines = [f"💱 <b>{base} Exchange Rates</b>", f"🕒 {now_str()}", ""]
    for c in FIAT_CURRENCIES:
        if c == base:
            continue
        lines.append(f"1 {base} = <b>{rates[c]:.4f}</b> {c}")
    return "\n".join(lines)


def build_crypto_message(symbol):
    coin_id = CRYPTO_IDS[symbol]
    data = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd,eur,mad", "include_24hr_change": "true"},
        timeout=10,
    ).json()
    info = data[coin_id]
    change = info.get("usd_24h_change", 0)
    arrow = "🟢" if change >= 0 else "🔴"
    lines = [
        f"🪙 <b>{symbol} Price</b>",
        f"🕒 {now_str()}",
        "",
        f"💵 {info['usd']:.4f} USD",
        f"💶 {info.get('eur', 0):.4f} EUR",
        f"🇲🇦 {info.get('mad', 0):.2f} MAD",
        "",
        f"{arrow} 24h Change: {change:.2f}%",
    ]
    return "\n".join(lines)


@bot.message_handler(commands=["start"])
def start(message):
    remove_old_keyboard(message.chat.id)
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


@bot.callback_query_handler(func=lambda c: c.data == "menu_fiat")
def cb_fiat_menu(call):
    bot.edit_message_text(
        "💱 <b>Select a base currency:</b>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=fiat_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "menu_crypto")
def cb_crypto_menu(call):
    bot.edit_message_text(
        "🪙 <b>Select a cryptocurrency:</b>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=crypto_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("fiat_"))
def cb_show_fiat(call):
    base = call.data.split("_")[1]
    try:
        text = build_fiat_message(base)
    except Exception:
        text = "⚠️ Could not fetch rates right now. Please try again."
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=back_button("fiat"),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("crypto_"))
def cb_show_crypto(call):
    symbol = call.data.split("_")[1]
    try:
        text = build_crypto_message(symbol)
    except Exception:
        text = "⚠️ Could not fetch price right now. Please try again."
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=back_button("crypto"),
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
        "💱 <b>Fiat Currencies</b> — tap a currency to see live exchange rates.\n"
        "🪙 <b>Crypto Currencies</b> — tap a coin to see its live price.\n"
        "🧮 <b>Calculator</b> — send any math expression directly.\n\n"
        "All data updates live each time you check it.",
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
