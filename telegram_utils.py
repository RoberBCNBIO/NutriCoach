# telegram_utils.py

import os, httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ---------- función base ----------
async def tg(method: str, payload: dict):
    url = f"{TG_API}/{method}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        # ⚠️ fix: no crashear si answerCallbackQuery llega tarde
        if r.status_code == 400 and method == "answerCallbackQuery":
            print("[INFO] Ignorando callback viejo:", r.text)
            return None
        r.raise_for_status()
        return r.json()

# ---------- utilidades ----------
async def answer_callback(callback_id: str, text: str = ""):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        return await tg("answerCallbackQuery", payload)
    except Exception as e:
        # seguridad extra
        print("[WARN] answerCallback falló:", e)
        return None

async def edit_message(chat_id: str, message_id: int, text: str, reply_markup: dict = None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg("editMessageText", payload)
