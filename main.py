# main.py

import os, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from onboarding import start_onboarding, ask_next, save_answer, kb_reset_confirm
from telegram_utils import tg, answer_callback

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI()
init_db()

@app.on_event("startup")
async def startup_event():
    if TELEGRAM_BOT_TOKEN and PUBLIC_BASE_URL:
        webhook_url = f"{PUBLIC_BASE_URL.rstrip('/')}/webhook"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.post(api_url, json={"url": webhook_url})
                r.raise_for_status()
                print("✅ Webhook configurado:", r.json())
            except Exception as e:
                print("❌ Error configurando webhook:", e)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    callback = data.get("callback_query", {})

    chat_id = None
    text = None
    is_callback = False

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
    elif callback:
        is_callback = True
        chat_id = callback["message"]["chat"]["id"]
        text = callback.get("data", "")

    if not chat_id:
        return PlainTextResponse("no chat_id")

    # --- Comando start ---
    if text and text.startswith("/start"):
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if u:
                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "⚠️ Ya tienes un perfil configurado. ¿Quieres sobrescribirlo?",
                    "reply_markup": kb_reset_confirm()
                })
        return await start_onboarding(chat_id)

    # --- Confirmación de reset ---
    if is_callback and text in ("reset_yes", "reset_no"):
        if text == "reset_yes":
            with SessionLocal() as s:
                u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                if u:
                    s.delete(u)
                    s.commit()
            return await start_onboarding(chat_id)
        else:
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "👌 Mantendré tu perfil actual."
            })

    # --- Onboarding (igual que antes) ---
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if u and u.onboarding_step != 0:
            field_map = {
                1: "sexo", 2: "edad", 3: "altura_cm", 4: "peso_kg",
                5: "actividad", 6: "objetivo_detallado", 7: "estilo_dieta",
                8: "preferencias", 9: "no_gustos", 10: "alergias",
                11: "vetos", 12: "tiempo_cocina", 13: "equipamiento",
                14: "duracion_plan_semanas", 15: "pais",
            }
            field = field_map.get(u.onboarding_step)
            if field:
                if is_callback:
                    raw_value = text
                    if "_" in raw_value:
                        raw_value = raw_value.split("_", 1)[-1]
                    await save_answer(chat_id, field, raw_value)
                    await answer_callback(callback["id"])
                else:
                    await save_answer(chat_id, field, text)
            return await ask_next(chat_id)

    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})

@app.get("/health")
async def health():
    return {"status": "ok"}
