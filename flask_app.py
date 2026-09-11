import os
import io
import logging
import requests
import fitz  # PyMuPDF
from PIL import Image
import telebot
from telebot import types
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DocBot")

TOKEN = "8966729910:AAECEcUt0JREMxTYKDzH1wk65A2Ffj6324o"
BASE_URL = "https://telegram-bot-production-7d43.up.railway.app"
BRAND_NAME = "DocBot"
OCR_API_KEY = "helloworld"  # Free demo key. Get your own at ocr.space for production use.

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# In-memory state: chat_id -> pending action
user_state = {}

STAR_OPTIONS = [1, 15, 25, 50, 100, 250]


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📄  Extract Text", callback_data="nav:extract"))
    kb.add(types.InlineKeyboardButton("🔄  Convert Format", callback_data="nav:convert"))
    kb.add(types.InlineKeyboardButton("💛  Support", callback_data="nav:support"))
    return kb


def kb_convert_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🖼️  Image → PDF", callback_data="conv:img2pdf"))
    kb.add(types.InlineKeyboardButton("📄  PDF → Image", callback_data="conv:pdf2img"))
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


def kb_back_main():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


def kb_support():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[types.InlineKeyboardButton(f"⭐ {n}", callback_data=f"star:{n}") for n in STAR_OPTIONS])
    kb.add(types.InlineKeyboardButton("🏠  Main Menu", callback_data="nav:main"))
    return kb


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------

def welcome_text(name):
    return (
        f"<b>Welcome to {BRAND_NAME}, {name}.</b>\n"
        "──────────────────────\n"
        "Extract text from images and PDFs, or convert "
        "between image and PDF formats — instantly.\n\n"
        "Choose an option below."
    )


def extract_prompt_text():
    return (
        "<b>📄 Extract Text</b>\n"
        "──────────────────────\n"
        "Send me a photo or a PDF file, and I'll extract "
        "the text from it automatically."
    )


def convert_menu_text():
    return "<b>🔄 Convert Format</b>\n──────────────────────\nChoose a conversion type:"


def img2pdf_prompt_text():
    return "<b>🖼️ Image → PDF</b>\n──────────────────────\nSend me the image you want to convert."


def pdf2img_prompt_text():
    return "<b>📄 PDF → Image</b>\n──────────────────────\nSend me the PDF file you want to convert."


def support_text():
    return (
        "<b>💛 Support This Bot</b>\n"
        "──────────────────────\n"
        "If you find this bot useful, you can support its "
        "development with Telegram Stars.\n\n"
        "Choose an amount below:"
    )


def error_text(msg):
    return f"⚠️ <b>Something went wrong</b>\n{msg}"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def download_file(file_id):
    file_info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def ocr_extract_text(file_bytes, filename):
    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files={"file": (filename, file_bytes)},
        data={"apikey": OCR_API_KEY, "language": "eng", "isOverlayRequired": False},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("IsErroredOnProcessing"):
        raise ValueError(data.get("ErrorMessage", ["OCR failed"])[0])
    parsed = data.get("ParsedResults", [])
    if not parsed:
        raise ValueError("No text detected")
    return parsed[0].get("ParsedText", "").strip()


def image_bytes_to_pdf(img_bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    output = io.BytesIO()
    img.save(output, format="PDF")
    output.seek(0)
    return output


def pdf_bytes_to_images(pdf_bytes, max_pages=5):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(dpi=150)
        buf = io.BytesIO(pix.tobytes("png"))
        buf.seek(0)
        images.append(buf)
    doc.close()
    return images


# ---------------------------------------------------------------------------
# Navigation handlers
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message):
    user_state.pop(message.chat.id, None)
    bot.send_message(message.chat.id, welcome_text(message.from_user.first_name or "there"), reply_markup=kb_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:main")
def nav_main(call):
    user_state.pop(call.message.chat.id, None)
    bot.edit_message_text(welcome_text(call.from_user.first_name or "there"),
                           call.message.chat.id, call.message.message_id, reply_markup=kb_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:extract")
def nav_extract(call):
    user_state[call.message.chat.id] = "extract"
    bot.edit_message_text(extract_prompt_text(), call.message.chat.id, call.message.message_id, reply_markup=kb_back_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:convert")
def nav_convert(call):
    user_state.pop(call.message.chat.id, None)
    bot.edit_message_text(convert_menu_text(), call.message.chat.id, call.message.message_id, reply_markup=kb_convert_menu())


@bot.callback_query_handler(func=lambda c: c.data == "conv:img2pdf")
def nav_img2pdf(call):
    user_state[call.message.chat.id] = "img2pdf"
    bot.edit_message_text(img2pdf_prompt_text(), call.message.chat.id, call.message.message_id, reply_markup=kb_back_main())


@bot.callback_query_handler(func=lambda c: c.data == "conv:pdf2img")
def nav_pdf2img(call):
    user_state[call.message.chat.id] = "pdf2img"
    bot.edit_message_text(pdf2img_prompt_text(), call.message.chat.id, call.message.message_id, reply_markup=kb_back_main())


@bot.callback_query_handler(func=lambda c: c.data == "nav:support")
def nav_support(call):
    bot.edit_message_text(support_text(), call.message.chat.id, call.message.message_id, reply_markup=kb_support())


# ---------------------------------------------------------------------------
# Telegram Stars payment
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("star:"))
def send_star_invoice(call):
    amount = int(call.data.split(":")[1])
    bot.send_invoice(
        call.message.chat.id,
        title="Support DocBot",
        description=f"Thank you for supporting DocBot with {amount} Stars!",
        invoice_payload=f"support_{amount}",
        provider_token="",  # Empty for Telegram Stars
        currency="XTR",
        prices=[types.LabeledPrice(label="Support", amount=amount)],
    )


@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(pre_checkout_q):
    bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def payment_success(message):
    bot.send_message(
        message.chat.id,
        "💛 <b>Thank you for your support!</b>\nIt truly helps keep this bot running.",
        reply_markup=kb_back_main(),
    )


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

@bot.message_handler(content_types=["photo", "document"])
def handle_file(message):
    chat_id = message.chat.id
    action = user_state.get(chat_id)

    if not action:
        bot.send_message(chat_id, "Please choose an option from the menu first.", reply_markup=kb_main())
        return

    try:
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
            filename = "image.jpg"
        else:
            file_id = message.document.file_id
            filename = message.document.file_name or "file"

        file_bytes = download_file(file_id)
        processing_msg = bot.send_message(chat_id, "⏳ Processing...")

        if action == "extract":
            text = ocr_extract_text(file_bytes, filename)
            result = text if text else "No text was detected in this file."
            bot.edit_message_text(f"<b>📄 Extracted Text</b>\n──────────────────────\n{result}",
                                   chat_id, processing_msg.message_id)
            bot.send_message(chat_id, "What would you like to do next?", reply_markup=kb_main())

        elif action == "img2pdf":
            pdf_buf = image_bytes_to_pdf(file_bytes)
            bot.delete_message(chat_id, processing_msg.message_id)
            bot.send_document(chat_id, pdf_buf, visible_file_name="converted.pdf",
                               caption="✅ Here's your PDF.")
            bot.send_message(chat_id, "What would you like to do next?", reply_markup=kb_main())

        elif action == "pdf2img":
            images = pdf_bytes_to_images(file_bytes)
            bot.delete_message(chat_id, processing_msg.message_id)
            if not images:
                bot.send_message(chat_id, "⚠️ Could not read this PDF.")
            else:
                for idx, img_buf in enumerate(images, start=1):
                    bot.send_photo(chat_id, img_buf, caption=f"Page {idx}/{len(images)}")
                bot.send_message(chat_id, "✅ Conversion complete. What's next?", reply_markup=kb_main())

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        bot.send_message(chat_id, error_text("Please try again with a different file."), reply_markup=kb_main())

    finally:
        user_state.pop(chat_id, None)


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    bot.send_message(message.chat.id, welcome_text(message.from_user.first_name or "there"), reply_markup=kb_main())


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
