import os
import re
import logging
from datetime import datetime, timezone
import requests
import telebot
from telebot import types
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ValueX")

TOKEN = "8966729910:AAECEcUt0JREMxTYKDzH1wk65A2Ffj6324o"
BASE_URL = "https://telegram-bot-production-7d43.up.railway.app"
BRAND_NAME = "ValueX"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

FIAT_CURRENCIES = ["USD", "EUR", "GBP", "MAD", "SAR", "AED", "JPY", "CNY"]

CRYPTO_ASSETS = {
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

CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "MAD": "🇲🇦",
    "SAR": "🇸🇦", "AED": "🇦🇪", "JPY": "🇯🇵", "CNY": "🇨🇳",
}

CALC_PATTERN = re.compile(r"^[\d\.\+\-\*\/\(\)\s]+$")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def timestamp():
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def divider():
    return "─" * 24


def safe_edit(call, text, markup=None):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Edit failed, sending new message instead: {e}")
        bot.send_message(call.message.chat.id, text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💱  Fiat Rates", callback_data="nav:fiat"),
        types.InlineKeyboardButton("🪙  Crypto Prices", callback_data="nav:crypto"),
    )
    kb.add(
        types.InlineKeyboardButton("🧮  Calculator", callback_data="nav:calc"),
        types.InlineKeyboardButton("ℹ️  About", callback_data="nav:about"),
    )
    return kb


def kb_fiat_list():
    kb = types.InlineKeyboardMarkup(row_width=4)
    kb.add(*[
        types.InlineKeyboardButton(f"{CURRENCY_FLAGS.get(c,'')} {c}", callback_data=f"fiat:{c}")
        for c in FIAT_CURRENCIES
    ])
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


def kb_crypto_list():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[types.InlineKeyboardButton(c, callback_data=f"crypto:{c}") for c in CRYPTO_ASSETS])
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


def kb_result(back_target):
    kb = types.InlineKeyboardMarkup(row_width=1)
    label = "🔁  Choose Another Currency" if back_target == "fiat" else "🔁  Choose Another Asset"
    kb.add(types.InlineKeyboardButton(label, callback_data=f"nav:{back_target}"))
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


def kb_back_main():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def fetch_fiat_rates(base):
    r = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        raise ValueError("API returned an error")
    return data["rates"]


def fetch_crypto_price(symbol):
    coin_id = CRYPTO_ASSETS[symbol]
    r = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": coin_id,
            "vs_currencies": "usd,eur,mad",
            "include_24hr_change": "true",
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if coin_id not in data:
        raise ValueError("Asset not found")
    return data[coin_id]


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def welcome_text(name):
    return (
        f"<b>Welcome to {BRAND_NAME}, {name}.</b>\n"
        f"{divider()}\n"
        "Your real-time companion for currency exchange rates "
        "and cryptocurrency prices.\n\n"
        "Select an option below to get started."
    )


def about_text():
    return (
        f"<b>{BRAND_NAME}</b>\n"
        f"{divider()}\n"
        "A lightweight financial data assistant.\n\n"
        "💱  <b>Fiat Rates</b> — live exchange rates for 8 major currencies.\n"
        "🪙  <b>Crypto Prices</b> — live prices for the 10 most traded assets.\n"
        "🧮  <b>Calculator</b> — quick arithmetic, no app switching.\n\n"
        "All data is fetched live at the moment of your request."
    )


def calc_text():
    return (
        "<b>Calculator</b>\n"
        f"{divider()}\n"
        "Send any arithmetic expression directly in the chat, for example:\n\n"
        "<code>250 * 4</code>\n"
        "<code>(120 + 80) / 2</code>\n"
        "<code>15 ** 2</code>"
    )


def fiat_result_text(base, rates):
    lines = [
        f"<b>{CURRENCY_FLAGS.get(base,'')} {base} — Exchange Rates</b>",
        f"🕒 {timestamp()}",
        divider(),
    ]
    for c in FIAT_CURRENCIES:
        if c == base:
            continue
        flag = CURRENCY_FLAGS.get(c, "")
        lines.append(f"{flag} 1 {base}  =  <b>{rates[c]:.4f}</b> {c}")
    return "\n".join(lines)


def crypto_result_text(symbol, info):
    change = info.get("usd_24h_change", 0.0)
    trend = "🟢 ▲" if change >= 0 else "🔴 ▼"
    lines = [
        f"<b>🪙 {symbol} — Live Price</b>",
        f"🕒 {timestamp()}",
        divider(),
        f"💵  {info['usd']:,.4f} USD",
        f"💶  {info.get('eur', 0):,.4f} EUR",
        f"🇲🇦  {info.get('mad', 0):,.2f} MAD",
        divider(),
        f"{trend}  24h change: {change:.2f}%",
    ]
    return "\n".join(lines)


def error_text(context):
    return (
        f"⚠️ <b>Temporarily unavailable</b>\n"
        f"We couldn't fetch {context} right now. Please try again in a moment."
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        welcome_text(message.from_user.first_name or "there"),
        reply_markup=kb_main(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "nav:main")
def nav_main(call):
    safe_edit(call, welcome_text(call.from_user.first_name or "there"), kb_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:fiat")
def nav_fiat(call):
    safe_edit(call, "<b>💱 Select a base currency</b>", kb_fiat_list())


@bot.callback_query_handler(func=lambda c: c.data == "nav:crypto")
def nav_crypto(call):
    safe_edit(call, "<b>🪙 Select a cryptocurrency</b>", kb_crypto_list())


@bot.callback_query_handler(func=lambda c: c.data == "nav:calc")
def nav_calc(call):
    safe_edit(call, calc_text(), kb_back_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:about")
def nav_about(call):
    safe_edit(call, about_text(), kb_back_main())


@bot.callback_query_handler(func=lambda c: c.data.startswith("fiat:"))
def show_fiat(call):
    base = call.data.split(":")[1]
    try:
        rates = fetch_fiat_rates(base)
        text = fiat_result_text(base, rates)
    except Exception as e:
        logger.error(f"Fiat fetch failed: {e}")
        text = error_text("exchange rates")
    safe_edit(call, text, kb_result("fiat"))


@bot.callback_query_handler(func=lambda c: c.data.startswith("crypto:"))
def show_crypto(call):
    symbol = call.data.split(":")[1]
    try:
        info = fetch_crypto_price(symbol)
        text = crypto_result_text(symbol, info)
    except Exception as e:
        logger.error(f"Crypto fetch failed: {e}")
        text = error_text("this asset's price")
    safe_edit(call, text, kb_result("crypto"))


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    text = message.text.strip()

    if CALC_PATTERN.match(text) and any(ch.isdigit() for ch in text):
        try:
            result = eval(text, {"__builtins__": {}}, {})
            bot.send_message(
                message.chat.id,
                f"🧮 <code>{text}</code>  =  <b>{result}</b>",
            )
        except Exception:
            bot.send_message(message.chat.id, "⚠️ That expression couldn't be calculated.")
        return

    bot.send_message(
        message.chat.id,
        welcome_text(message.from_user.first_name or "there"),
        reply_markup=kb_main(),
    )


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")
    return f"{BRAND_NAME} — Webhook set successfully.", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
