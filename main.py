# main.py

import os, httpx, openai
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from onboarding import start_onboarding, ask_next, save_answer, kb_reset_confirm, kb_main_menu
from telegram_utils import tg, answer_callback
from prompts import SYSTEM_PROMPT, COACH_STYLE_SUFFIX

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

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

    # --- Comando /start ---
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

    # --- Confirmación reset ---
    if is_callback and text in ("reset_yes", "reset_no"):
        await answer_callback(callback["id"])
        if text == "reset_yes":
            with SessionLocal() as s:
                u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                if u:
                    s.delete(u)
                    s.commit()
            return await start_onboarding(chat_id)
        else:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "👌 Mantendré tu perfil actual."})

    # --- Comando /menu para salir del chat libre ---
    if text and text.startswith("/menu"):
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if u and u.vetos == "__chat__":
                u.vetos = None
                s.commit()
        return await tg("sendMessage", {
            "chat_id": chat_id,
            "text": "Volvemos al menú principal:",
            "reply_markup": kb_main_menu()
        })

    # --- Onboarding flujo normal ---
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()

        if u and u.onboarding_step != 0:
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
                if is_callback:
                    await answer_callback(callback["id"])
                    raw_value = text
                    if "_" in raw_value:
                        raw_value = raw_value.split("_", 1)[-1]
                    await save_answer(chat_id, field, raw_value)
                else:
                    await save_answer(chat_id, field, text)
            return await ask_next(chat_id)

        # --- Menú principal callbacks ---
        if is_callback and text.startswith("menu_"):
            await answer_callback(callback["id"])
            if text == "menu_generate":
                return await tg("sendMessage", {"chat_id": chat_id, "text": "📅 (Aquí generaremos tu dieta completa semana a semana)"})
            if text == "menu_shopping":
                return await tg("sendMessage", {"chat_id": chat_id, "text": "🛒 (Aquí generaremos tu lista de la compra)"})
            if text == "menu_profile":
                perfil_txt = f"""
👤 <b>Tu perfil</b>
Sexo: {u.sexo}
Edad: {u.edad}
Altura: {u.altura_cm} cm
Peso: {u.peso_kg} kg
Actividad: {u.actividad}
Objetivos: {u.objetivo_detallado}
Estilos: {u.estilo_dieta}
Equipamiento: {u.equipamiento}
Semanas plan: {u.duracion_plan_semanas}
País: {u.pais}
"""
                return await tg("sendMessage", {"chat_id": chat_id, "text": perfil_txt, "parse_mode": "HTML"})
            if text == "menu_chat":
                # Activamos modo chat guardando un flag en vetos
                with SessionLocal() as s:
                    u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                    if u:
                        u.vetos = "__chat__"
                        s.commit()
                return await tg("sendMessage", {"chat_id": chat_id, "text": "💬 Estoy listo para chatear contigo. Escríbeme lo que quieras sobre recetas, listas o dieta. (Escribe /menu para volver al menú)"})
            if text == "menu_help":
                help_txt = """❓ <b>Ayuda</b>

• 📅 Generar dieta completa → crea tu plan semana a semana.
• 🛒 Lista de la compra → consolida los ingredientes de tu plan.
• ℹ️ Ver mi perfil → repasa la información que configuraste.
• 💬 Chat con coach → hazme preguntas o pide cambios.
• /start → reinicia (te preguntará si quieres sobrescribir).
• /menu → salir del chat libre y volver al menú.
"""
                return await tg("sendMessage", {"chat_id": chat_id, "text": help_txt, "parse_mode": "HTML"})

        # --- CHAT LIBRE ---
        if u and u.vetos == "__chat__" and not is_callback and text and not text.startswith("/"):
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=OPENAI_TEMPERATURE,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text + "\n\n" + COACH_STYLE_SUFFIX}
                ]
            )
            answer = completion.choices[0].message.content
            return await tg("sendMessage", {"chat_id": chat_id, "text": answer})

    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})


@app.get("/health")
async def health():
    return {"status": "ok"}
