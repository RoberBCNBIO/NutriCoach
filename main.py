# main.py

import os, httpx, openai, json, re
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from datetime import datetime

from db import init_db, SessionLocal, User, MenuLog
from onboarding import start_onboarding, ask_next, save_answer, kb_reset_confirm, kb_main_menu
from telegram_utils import tg, answer_callback

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
                # Recuperar perfil
                perfil_txt = f"""
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

                # Generar dieta con OpenAI
                client = openai.OpenAI(api_key=OPENAI_API_KEY)
                completion = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    temperature=OPENAI_TEMPERATURE,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un nutricionista experto. "
                                "Debes responder ÚNICAMENTE con un JSON válido, sin texto adicional. "
                                "Formato esperado:\n\n"
                                "{\n"
                                '  \"duracion_semanas\": <int>,\n'
                                '  \"semanas\": [ { \"semana\": 1, \"dias\": { \"lunes\": { \"desayuno\": {\"comida\":..., \"cantidad\":...}, ... } } } ]\n'
                                "}"
                            )
                        },
                        {"role": "user", "content": f"Genera una dieta en JSON según este perfil:\n{perfil_txt}"}
                    ]
                )
                raw_text = completion.choices[0].message.content.strip()

                # Extraer solo JSON
                match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                if match:
                    dieta_json = match.group(0)
                else:
                    dieta_json = "{}"

                # Validar JSON
                try:
                    parsed = json.loads(dieta_json)
                except Exception as e:
                    print("[ERROR] JSON inválido:", e)
                    parsed = {}

                # Guardar en DB (como dict, no string)
                log = MenuLog(
                    chat_id=str(chat_id),
                    params=perfil_txt,
                    menu_json=parsed,
                    timestamp=datetime.utcnow()
                )
                s.add(log)
                s.commit()

                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "📅 Tu dieta completa ha sido generada y guardada. Ahora puedes consultarla en el chat libre o pedirme la lista de la compra."
                })

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
                # Guardamos modo chat y construimos contexto (perfil + dieta si existe)
                with SessionLocal() as s2:
                    u2 = s2.query(User).filter(User.chat_id == str(chat_id)).first()
                    if u2:
                        u2.vetos = "__chat__"

                        perfil_txt = f"""
Perfil usuario:
Sexo: {u2.sexo}
Edad: {u2.edad}
Altura: {u2.altura_cm} cm
Peso: {u2.peso_kg} kg
Actividad: {u2.actividad}
Objetivos: {u2.objetivo_detallado}
Estilos: {u2.estilo_dieta}
Equipamiento: {u2.equipamiento}
Semanas plan: {u2.duracion_plan_semanas}
País: {u2.pais}
"""

                        dieta_txt = ""
                        try:
                            last_menu = s2.query(MenuLog).order_by(MenuLog.timestamp.desc()).first()
                            if last_menu and getattr(last_menu, "menu_json", None):
                                dieta_txt = f"\nDieta actual (resumen):\n{json.dumps(last_menu.menu_json)[:500]}..."
                        except Exception as e:
                            print("[WARN] No se pudo recuperar dieta:", e)
                            s2.rollback()

                        u2.preferencias = perfil_txt + dieta_txt
                        try:
                            s2.commit()
                        except Exception as e:
                            print("[ERROR] Falló commit en menu_chat:", e)
                            s2.rollback()

                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "💬 Estoy listo para chatear contigo teniendo en cuenta tu perfil y (si existe) tu dieta actual. Escríbeme lo que quieras sobre recetas, listas o ajustes. (Escribe /menu para volver al menú)"
                })
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

        # --- CHAT LIBRE (natural con perfil + dieta si existe) ---
        if u and u.vetos == "__chat__" and not is_callback and text:
            context = u.preferencias or ""
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=OPENAI_TEMPERATURE,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un coach nutricional cercano, simpático y natural. "
                            "Responde de forma conversacional, breve si procede, como si chatearas en Telegram. "
                            "Ten siempre en cuenta el siguiente perfil y dieta del usuario:\n\n"
                            f"{context}"
                        )
                    },
                    {"role": "user", "content": text}
                ]
            )
            answer = completion.choices[0].message.content
            return await tg("sendMessage", {"chat_id": chat_id, "text": answer})

    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})


@app.get("/health")
async def health():
    return {"status": "ok"}
