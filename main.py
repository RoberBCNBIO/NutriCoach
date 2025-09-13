# main.py

import os, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from onboarding import start_onboarding, ask_next, save_answer
from telegram_utils import tg

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI()
init_db()


# ---------- Webhook principal ----------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    callback = data.get("callback_query", {})

    chat_id = None
    text = None

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
    elif callback:
        chat_id = callback["message"]["chat"]["id"]
        text = callback["data"]

    if not chat_id:
        return PlainTextResponse("no chat_id")

    # --- Comandos ---
    if text == "/start":
        return await start_onboarding(chat_id)

    if text == "/reset":
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if u:
                s.delete(u)
                s.commit()
        return await start_onboarding(chat_id)

    if text == "/menu" or text == "/macros":
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if not u or u.onboarding_step != 0:
                return await ask_next(chat_id)
        # aquí iría la lógica real de /menu o /macros
        return await tg("sendMessage", {"chat_id": chat_id, "text": f"📊 Aquí iría tu respuesta de {text}."})

    # --- Onboarding (respuestas normales) ---
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if u and u.onboarding_step != 0:
            # determinar qué campo toca
            step = u.onboarding_step
            field_map = {
                1: "sexo",
                2: "edad",
                3: "altura_cm",
                4: "peso_kg",
                5: "actividad",
                6: "objetivo_detallado",
                7: "estilo_dieta",
                8: "preferencias",
                9: "no_gustos",
                10: "alergias",
                11: "vetos",
                12: "tiempo_cocina",
                13: "equipamiento",
                14: "duracion_plan_semanas",
                15: "pais",
            }
            field = field_map.get(step)
            if field:
                await save_answer(chat_id, field, text)

            return await ask_next(chat_id)

    # Si llega aquí y no es onboarding
    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})


# ---------- Health check ----------
@app.get("/health")
async def health():
    return {"status": "ok"}
