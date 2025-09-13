# telegram_utils.py

import os
import httpx
import logging
from dotenv import load_dotenv

# --- Configuración ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN no está configurado en .env o en Railway")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logger = logging.getLogger(__name__)


# --- Cliente Telegram ---
async def tg(method: str, payload: dict = None, http_method: str = "POST") -> dict:
    """Llamadas a la API de Telegram"""
    async with httpx.AsyncClient(timeout=15) as client:
        url = f"{TG_API}/{method}"
        try:
            if http_method == "GET":
                r = await client.get(url, params=payload or {})
            else:
                r = await client.post(url, json=payload or {})
            r.raise_for_status()
            return r.json()
        except httpx.RequestError as e:
            logger.error(f"[Telegram API] Error de conexión: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[Telegram API] Error HTTP {e.response.status_code}: {e.response.text}")
            raise


# --- Funciones helper ---
async def send_message(chat_id: int | str, text: str, reply_markup: dict = None, parse_mode: str = "HTML"):
    """Enviar mensaje de texto a un chat"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg("sendMessage", payload)


async def answer_callback(callback_query_id: str, text: str = "", show_alert: bool = False):
    """Responder a una interacción de inline keyboard"""
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }
    return await tg("answerCallbackQuery", payload)


async def edit_message(chat_id: int | str, message_id: int, text: str, reply_markup: dict = None, parse_mode: str = "HTML"):
    """Editar mensaje existente"""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg("editMessageText", payload)
