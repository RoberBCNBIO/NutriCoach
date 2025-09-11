import os, json, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from nutrition import mifflin_st_jeor, tdee, objetivo_kcal, calcular_macros, plantilla_plan_dia
from db import init_db, SessionLocal, User, CheckIn, MenuLog
from prompts import SYSTEM_PROMPT, USER_GUIDANCE, COACH_STYLE_SUFFIX

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI()
init_db()

# ---------- Telegram ----------
async def tg(method: str, payload: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{TG_API}/{method}", json=payload)
        r.raise_for_status()
        return r.json()

def kb_main():
    return {
        "inline_keyboard": [[
            {"text":"📊 Calcular macros","callback_data":"macros"},
            {"text":"🥗 Menú 3 días","callback_data":"menu3"}
        ],[
            {"text":"✅ Check-in diario","callback_data":"checkin"},
            {"text":"ℹ️ Ayuda","callback_data":"help"}
        ]]
    }

# ---------- OpenAI ----------
async def call_openai(messages):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"}
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
    return session.query(User).filter(User.chat_id==str(chat_id)).first()

async def ensure_onboarded(chat_id: str):
    with SessionLocal() as s:
        u = get_user(s, chat_id)
        if not u or not (u.sexo and u.edad and u.altura_cm and u.peso_kg):
            await tg("sendMessage", {"chat_id": chat_id,
                "text":"Necesito tus datos básicos. Envíame este formato:\n\n"
                       "Sexo (M/F):\nEdad:\nAltura (cm):\nPeso (kg):\nActividad (sedentaria/ligera/moderada/alta/muy alta):\nObjetivo (perder/mantener/ganar):\nAlergias/Vetos:\nEquipamiento (ej. air fryer):\nTiempo cocina (min):",
                "reply_markup": {"inline_keyboard":[[{"text":"Abrir menú","callback_data":"menu"}]]}
            })
            return False
    return True

# ---------- Handlers de comandos ----------
async def do_macros(chat_id: str):
    with SessionLocal() as s:
        u = get_user(s, chat_id)
        if not u: return await ensure_onboarded(chat_id)
        bmr = mifflin_st_jeor(u.sexo, u.peso_kg, u.altura_cm, u.edad)
        tdee_val = tdee(bmr, u.actividad)
        kcal_obj = objetivo_kcal(tdee_val, u.objetivo)
        m = calcular_macros(u.peso_kg, kcal_obj)
    text = (f"Objetivo diario:\n"
            f"• Calorías: {m['kcal']} kcal\n"
            f"• Proteínas: {m['prote_g']} g\n"
            f"• Grasas: {m['grasa_g']} g\n"
            f"• Carbos: {m['carbo_g']} g\n")
    await tg("sendMessage", {"chat_id": chat_id, "text": text})

async def do_menu3(chat_id: str):
    with SessionLocal() as s:
        u = get_user(s, chat_id)
        if not u: return await ensure_onboarded(chat_id)
        bmr = mifflin_st_jeor(u.sexo, u.peso_kg, u.altura_cm, u.edad)
        kcal = round(objetivo_kcal(tdee(bmr, u.actividad), u.objetivo))
    dias = [plantilla_plan_dia(kcal) for _ in range(3)]
    menu = {"kcal_obj": kcal, "dias": dias}
    with SessionLocal() as s:
        s.add(MenuLog(chat_id=str(chat_id), params={"kcal":kcal}, menu_json=menu))
        s.commit()
    chunks = [f"Menú 3 días (~{kcal} kcal/día):"]
    for i, d in enumerate(dias, 1):
        chunks.append(
            f"\nDía {i}:\n• Des: {d['desayuno']}\n• Com: {d['comida']}\n• Cen: {d['cena']}\n• Snack: {d['snack']}"
        )
    await tg("sendMessage", {"chat_id": chat_id, "text": "\n".join(chunks)})

async def handle_free_text(chat_id: str, text: str):
    with SessionLocal() as s:
        u = get_user(s, chat_id)
    perfil = (f"Perfil: {u.sexo if u else '?'} {u.edad if u else '?'}a, {u.altura_cm if u else '?'}cm, {u.peso_kg if u else '?'}kg, "
              f"actividad {u.actividad if u else '?'}, objetivo {u.objetivo if u else '?'}, equipamiento {u.equipamiento if u else '-'}.")

    messages = [
        {"role":"system","content": SYSTEM_PROMPT},
        {"role":"user","content": f"{perfil}\nPregunta: {text}\n{COACH_STYLE_SUFFIX}\n{USER_GUIDANCE}"}
    ]
    reply = await call_openai(messages)
    await tg("sendMessage", {"chat_id": chat_id, "text": reply})

# ---------- Endpoints ----------
@app.get("/health")
async def health():
    return PlainTextResponse("ok")

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return PlainTextResponse("forbidden", status_code=403)

    update = await request.json()

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            await tg("sendMessage", {"chat_id": chat_id, "text": "¡Hola! Soy NutriCoach 🤝", "reply_markup": kb_main()})
        elif text.startswith("/macros"):
            await do_macros(chat_id)
        elif text.startswith("/menu"):
            await do_menu3(chat_id)
        else:
            await handle_free_text(chat_id, text)

    elif "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq.get("data")
        if data == "macros":
            await do_macros(chat_id)
        elif data == "menu3":
            await do_menu3(chat_id)
        elif data == "help":
            await tg("sendMessage", {"chat_id": chat_id, "text": USER_GUIDANCE})
        await tg("answerCallbackQuery", {"callback_query_id": cq["id"]})

    return PlainTextResponse("ok")

@app.on_event("startup")
async def set_webhook():
    if not PUBLIC_BASE_URL: return
    await tg("setWebhook", {
        "url": PUBLIC_BASE_URL + "/telegram/webhook",
        "secret_token": WEBHOOK_SECRET or None,
        "drop_pending_updates": True
    })
