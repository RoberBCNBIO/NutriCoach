import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from prompts import SYSTEM_PROMPT, USER_GUIDANCE, COACH_STYLE_SUFFIX
from onboarding import start_onboarding, ask_next
from telegram_utils import tg   # ✅ import limpio, no circular

load_dotenv()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

app = FastAPI()
init_db()

# ---------- OpenAI ----------
import httpx

async def call_openai(messages):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "temperature": OPENAI_TEMPERATURE,
        "messages": messages,
        "max_tokens": 500
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

# ---------- Funciones de negocio ----------
def get_user(session, chat_id: str) -> User | None:
    return session.query(User).filter(User.chat_id == str(chat_id)).first()

async def handle_onboarding_text(chat_id: str, text: str):
    """Procesa respuestas libres en el onboarding"""
    import re
    with SessionLocal() as s:
        u = get_user(s, chat_id)
        if not u:
            return await start_onboarding(chat_id)

        step = u.onboarding_step or 1
        raw = text.strip()

        try:
            if step == 2:   # edad
                u.edad = int(raw)
            elif step == 3: # altura
                cleaned = re.sub(r"[^0-9.,]", "", raw)
                u.altura_cm = int(float(cleaned.replace(",", ".")))
            elif step == 4: # peso
                cleaned = re.sub(r"[^0-9.,]", "", raw)
                if not cleaned:
                    raise ValueError("peso vacío")
                u.peso_kg = round(float(cleaned.replace(",", ".")), 1)
            elif step == 8: # no_gustos
                u.no_gustos = raw
            elif step == 9: # alergias
                u.alergias = raw
            elif step == 12: # duración plan
                u.duracion_plan_semanas = int(raw)
            else:
                return await ask_next(chat_id)

            u.onboarding_step = step + 1
            s.add(u)
            s.commit()

        except Exception as e:
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "⚠️ No he podido entender el número. Escribe solo cifras, ej: 70 o 70.5"
            })

    await ask_next(chat_id)


# ---------- Endpoints ----------
@app.get("/health")
async def health():
    return PlainTextResponse("ok")

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return PlainTextResponse("forbidden", status_code=403)

    update = await request.json()

    # --- Mensajes normales ---
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            await start_onboarding(chat_id)
        elif text.startswith("/plan"):
            with SessionLocal() as s:
                u = get_user(s, chat_id)
            if not u:
                await start_onboarding(chat_id)
            else:
                plan = (f"🎯 Plan actual:\n"
                        f"Objetivo: {u.objetivo_detallado or '-'}\n"
                        f"Dieta: {u.estilo_dieta or '-'}\n"
                        f"Duración: {u.duracion_plan_semanas or '-'} semanas\n"
                        f"Tiempo de cocina: {u.tiempo_cocina or '-'}\n"
                        f"Equipamiento: {u.equipamiento or '-'}\n"
                        f"Kcal objetivo: {u.kcal_objetivo or '-'}\n")
                await tg("sendMessage", {"chat_id": chat_id, "text": plan})
        else:
            with SessionLocal() as s:
                u = get_user(s, chat_id)
            if u and (u.onboarding_step or 0) > 0:
                await handle_onboarding_text(chat_id, text)
            else:
                # Chat libre al coach
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Usuario pregunta: {text}\n{COACH_STYLE_SUFFIX}\n{USER_GUIDANCE}"}
                ]
                reply = await call_openai(messages)
                await tg("sendMessage", {"chat_id": chat_id, "text": reply})

    # --- Callbacks de botones ---
    elif "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq.get("data")

        with SessionLocal() as s:
            u = get_user(s, chat_id) or User(chat_id=str(chat_id))

            if data.startswith("sexo_"):
                u.sexo = data.split("_", 1)[1]; u.onboarding_step = 2
            elif data.startswith("act_"):
                u.actividad = data.split("_", 1)[1]; u.onboarding_step = 6
            elif data.startswith("obj_"):
                mapping = {
                    "grasa": "perder grasa", "musculo": "ganar músculo", "abdomen": "definir abdomen",
                    "mente": "mente tranquila", "keto": "desinflamar", "cardio": "mejorar cardio",
                    "energia": "subir energía", "sueno": "dormir mejor"
                }
                key = data.split("_", 1)[1]
                u.objetivo_detallado = mapping.get(key, key); u.onboarding_step = 7
            elif data.startswith("dieta_"):
                u.estilo_dieta = data.split("_", 1)[1]; u.onboarding_step = 8
            elif data.startswith("cook_"):
                mapping = {"15": "≤15", "30": "~30", "45": ">45"}
                key = data.split("_", 1)[1]
                u.tiempo_cocina = mapping.get(key, key); u.onboarding_step = 11
            elif data.startswith("equip_"):
                eq = data.split("_", 1)[1]
                u.equipamiento = eq if eq != "none" else "ninguno"; u.onboarding_step = 12

            s.add(u); s.commit()

        await ask_next(chat_id)
        await tg("answerCallbackQuery", {"callback_query_id": cq["id"]})

    return PlainTextResponse("ok")

@app.on_event("startup")
async def set_webhook():
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not PUBLIC_BASE_URL or not TELEGRAM_BOT_TOKEN:
        return
    await tg("setWebhook", {
        "url": PUBLIC_BASE_URL + "/telegram/webhook",
        "secret_token": WEBHOOK_SECRET or None,
        "drop_pending_updates": True
    })
