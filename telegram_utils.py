import os, httpx
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def tg(method: str, payload: dict):
    """Llamadas a la API de Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN no está configurado en .env o en Railway")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{TG_API}/{method}", json=payload)
        r.raise_for_status()
        return r.json()
