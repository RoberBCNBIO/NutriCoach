# main.py

import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from onboarding import start_onboarding, ask_next, save_answer
from telegram_utils import tg, answer_callback

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI()
init_db()


# ---------- Helpers de normalización y validación ----------
def _normalize_command(txt: str) -> str:
    if not txt:
        return ""
    t = txt.strip().lower()
    # Acepta variantes tipo "start/" o "Start"
    if t.startswith(("start/", "start")):
        return "/start"
    return txt

def _normalize_callback_value(field: str, raw: str) -> tuple[str | None, str | None]:
    """
    Devuelve (valor_normalizado, error_msg)
    Si error_msg no es None, no avanzamos de step.
    """
    if not raw:
        return None, "No he recibido ninguna opción."

    # Todos los callback_data van con patrón tipo "sexo_M", "act_moderado", etc.
    payload = raw.split("_", 1)[-1] if "_" in raw else raw

    if field == "sexo":
        # Permitimos M/F/ND (ND no rompe nada, lo guardamos como "ND")
        if payload in ("M", "F", "ND"):
            return payload, None
        # Algunos teclados antiguos podían mandar "masculino"/"femenino"
        if payload.lower() in ("masculino", "m"):
            return "M", None
        if payload.lower() in ("femenino", "f"):
            return "F", None
        if payload.lower() in ("nd", "n/d", "none"):
            return "ND", None
        return None, "Opción de sexo no válida."

    if field == "actividad":
        # Botones actuales envían "sedentario", "ligero", "moderado", "alto", "muy_alto"
        # Estándar interno que usan tus cálculos:
        mapping = {
            "sedentario": "sedentaria",
            "sedentaria": "sedentaria",
            "ligero": "ligera",
            "ligera": "ligera",
            "moderado": "moderada",
            "moderada": "moderada",
            "alto": "alta",
            "alta": "alta",
            "muy_alto": "muy alta",
            "muyalta": "muy alta",
            "muy_alta": "muy alta",
            "muy alta": "muy alta",
        }
        val = mapping.get(payload.lower())
        if not val:
            return None, "Opción de actividad no válida."
        return val, None

    if field == "objetivo_detallado":
        # Guarda tal cual, pero podemos normalizar algunos alias
        aliases = {
            "grasa": "Perder grasa",
            "musculo": "Ganar músculo",
            "abdomen": "Definir abdomen",
            "mente": "Mente tranquila",
            "keto": "Desinflamar",
            "cardio": "Mejorar cardio",
            "energia": "Subir energía",
            "sueno": "Dormir mejor",
        }
        return aliases.get(payload, payload), None

    if field == "estilo_dieta":
        mapping = {
            "mediterranea": "Mediterránea",
            "japonesa": "Japonesa",
            "tailandesa": "Tailandesa",
            "arabe": "Árabe",
            "vegana": "Vegana",
            "americana": "Americana",
        }
        return mapping.get(payload, payload), None

    if field == "tiempo_cocina":
        # Esperamos cook_15 / cook_30 / cook_45  => guardar minutos como string "15" etc.
        if payload in ("15", "30", "45"):
            return payload, None
        if payload.startswith("cook_"):
            return payload.split("_", 1)[-1], None
        return None, "Opción de tiempo de cocina no válida."

    if field == "equipamiento":
        # Guardamos la etiqueta final (airfryer, horno, etc.)
        if payload in ("airfryer", "horno", "micro", "thermo", "none"):
            return payload, None
        # También aceptamos 'equip_airfryer' legacy
        if raw.startswith("equip_"):
            return raw.split("_", 1)[-1], None
        return payload, None

    if field == "duracion_plan_semanas":
        # Aunque venga vía botón en el futuro, validamos que sea número
        return payload, None

    if field == "pais":
        return payload, None

    # Para preferencias, no_gustos, alergias, vetos, etc. (si llegaran por botón)
    return payload, None


def _parse_int(txt: str, field_name: str) -> tuple[int | None, str | None]:
    try:
        return int(txt.strip()), None
    except Exception:
        return None, f"Escribe un número válido para {field_name}."

def _parse_float(txt: str, field_name: str) -> tuple[float | None, str | None]:
    txt = txt.replace(",", ".")
    try:
        return float(txt.strip()), None
    except Exception:
        return None, f"Escribe un número válido (puede incluir decimales) para {field_name}."


# ---------- Configurar webhook al arrancar ----------
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


# ---------- Webhook principal ----------
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
        text = message.get("text", "")
        text = _normalize_command(text)
    elif callback:
        is_callback = True
        chat_id = callback["message"]["chat"]["id"]
        text = callback.get("data", "")

    if not chat_id:
        return PlainTextResponse("no chat_id")

    # --- Comandos ---
    if text and text.startswith("/start"):
        return await start_onboarding(chat_id)

    if text and text.startswith("/reset"):
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if u:
                s.delete(u)
                s.commit()
        return await start_onboarding(chat_id)

    if text and (text.startswith("/menu") or text.startswith("/macros")):
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if not u or (u.onboarding_step or 0) != 0:
                return await ask_next(chat_id)
        return await tg("sendMessage", {"chat_id": chat_id, "text": f"📊 Aquí iría tu respuesta de {text}."})

    # --- Onboarding (respuestas normales o botones) ---
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            # Si alguien llega sin /start, iniciamos
            return await start_onboarding(chat_id)

        if (u.onboarding_step or 0) != 0:
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

            if not field:
                # Si por alguna razón no hay field, volvemos a preguntar
                return await ask_next(chat_id)

            if is_callback:
                value, err = _normalize_callback_value(field, text)
                # Responder SIEMPRE al callback para quitar el spinner
                try:
                    await answer_callback(callback["id"])
                except Exception:
                    pass

                if err:
                    return await tg("sendMessage", {"chat_id": chat_id, "text": f"⚠️ {err}"})
                if value is None:
                    return await tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Necesito una opción válida."})

                await save_answer(chat_id, field, str(value))
                return await ask_next(chat_id)

            # Respuesta escrita
            if field in ("edad", "altura_cm", "duracion_plan_semanas"):
                val, err = _parse_int(text, field)
                if err:
                    return await tg("sendMessage", {"chat_id": chat_id, "text": f"⚠️ {err}"})
                await save_answer(chat_id, field, str(val))
                return await ask_next(chat_id)

            if field == "peso_kg":
                val, err = _parse_float(text, field)
                if err:
                    return await tg("sendMessage", {"chat_id": chat_id, "text": f"⚠️ {err}"})
                await save_answer(chat_id, field, str(val))
                return await ask_next(chat_id)

            # Campos de texto libre
            await save_answer(chat_id, field, text)
            return await ask_next(chat_id)

    # Si llega aquí y no es onboarding
    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})


# ---------- Health check ----------
@app.get("/health")
async def health():
    return {"status": "ok"}
