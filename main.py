# main.py

import os, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from db import init_db, SessionLocal, User
from onboarding import (
    start_onboarding, ask_next, save_answer, kb_reset_confirm,
    load_list, kb_objetivo_multiselect, kb_estilo_multiselect, kb_equip_multiselect,
    save_list_toggle, advance_step
)
from telegram_utils import tg, answer_callback, edit_message

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

def _is_cmd(text: str, name: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return t == f"/{name}" or t.startswith(f"/{name}@")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    callback = data.get("callback_query", {})

    chat_id = None
    text = None
    is_callback = False
    message_id = None

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
    elif callback:
        is_callback = True
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        text = callback.get("data", "")

    if not chat_id:
        return PlainTextResponse("no chat_id")

    # --- /start con confirmación de sobrescritura ---
    if text and _is_cmd(text, "start"):
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

    # --- Comandos rápidos (si quisieras añadir /reset o similares) ---
    if text and text.startswith("/reset"):
        with SessionLocal() as s:
            u = s.query(User).filter(User.chat_id == str(chat_id)).first()
            if u:
                s.delete(u)
                s.commit()
        return await start_onboarding(chat_id)

    # ---------- ONBOARDING ----------
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()

        # Si no hay usuario y no es /start, iniciamos
        if not u:
            return await start_onboarding(chat_id)

        # Si estamos en onboarding...
        if (u.onboarding_step or 0) != 0:
            step = u.onboarding_step

            # --- MULTISELECT OBJETIVO (step 6) ---
            if step == 6 and is_callback:
                if text.startswith("obj_toggle_"):
                    await answer_callback(callback["id"])
                    key = text.replace("obj_toggle_", "", 1)
                    await save_list_toggle(chat_id, "objetivo_detallado", key)
                    # Recargar teclado con selección actual
                    u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                    sel = load_list(u.objetivo_detallado)
                    return await edit_message(chat_id, message_id,
                        "🎯 ¿Cuál es tu objetivo principal? (puedes elegir varias opciones y luego pulsa *Continuar*)",
                        reply_markup=kb_objetivo_multiselect(sel)
                    )
                if text == "obj_done":
                    await answer_callback(callback["id"])
                    sel = load_list(u.objetivo_detallado)
                    if not sel:
                        # alerta si no eligió nada
                        return await tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Elige al menos una opción antes de continuar."})
                    await advance_step(chat_id)
                    return await ask_next(chat_id)
                # cualquier otro callback en step 6 se ignora y se reimprime teclado
                sel = load_list(u.objetivo_detallado)
                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🎯 ¿Cuál es tu objetivo principal? (elige y pulsa *Continuar*)",
                    "reply_markup": kb_objetivo_multiselect(sel)
                })

            # --- MULTISELECT DIETA (step 7) ---
            if step == 7 and is_callback:
                if text.startswith("diet_toggle_"):
                    await answer_callback(callback["id"])
                    key = text.replace("diet_toggle_", "", 1)
                    await save_list_toggle(chat_id, "estilo_dieta", key)
                    u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                    sel = load_list(u.estilo_dieta)
                    return await edit_message(chat_id, message_id,
                        "🍽️ ¿Qué estilos de cocina prefieres? (elige varias y pulsa *Continuar*)",
                        reply_markup=kb_estilo_multiselect(sel)
                    )
                if text == "diet_done":
                    await answer_callback(callback["id"])
                    sel = load_list(u.estilo_dieta)
                    if not sel:
                        return await tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Elige al menos una opción antes de continuar."})
                    await advance_step(chat_id)
                    return await ask_next(chat_id)
                sel = load_list(u.estilo_dieta)
                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🍽️ ¿Qué estilos de cocina prefieres? (elige y pulsa *Continuar*)",
                    "reply_markup": kb_estilo_multiselect(sel)
                })

            # --- MULTISELECT EQUIPAMIENTO (step 13) ---
            if step == 13 and is_callback:
                if text.startswith("equip_toggle_"):
                    await answer_callback(callback["id"])
                    key = text.replace("equip_toggle_", "", 1)
                    await save_list_toggle(chat_id, "equipamiento", key)
                    u = s.query(User).filter(User.chat_id == str(chat_id)).first()
                    sel = load_list(u.equipamiento)
                    return await edit_message(chat_id, message_id,
                        "🔧 ¿Qué equipamiento tienes? (elige varias y pulsa *Continuar*)",
                        reply_markup=kb_equip_multiselect(sel)
                    )
                if text == "equip_done":
                    await answer_callback(callback["id"])
                    sel = load_list(u.equipamiento)
                    if not sel:
                        return await tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Elige al menos una opción antes de continuar."})
                    await advance_step(chat_id)
                    return await ask_next(chat_id)
                sel = load_list(u.equipamiento)
                return await tg("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🔧 ¿Qué equipamiento tienes? (elige y pulsa *Continuar*)",
                    "reply_markup": kb_equip_multiselect(sel)
                })

            # --- resto de pasos (simple o botones simples) ---
            field_map = {
                1: "sexo",
                2: "edad",
                3: "altura_cm",
                4: "peso_kg",
                5: "actividad",
                # 6 y 7 son multiselect (no usar save_answer aquí)
                # 8:
                8: "preferencias",
                9: "no_gustos",
                10: "alergias",
                11: "vetos",
                12: "tiempo_cocina",
                # 13 multiselect
                14: "duracion_plan_semanas",
                15: "pais",
            }
            field = field_map.get(step)

            if field:
                if is_callback:
                    # botones simples tipo "cook_30" o "sexo_M" etc.
                    await answer_callback(callback["id"])
                    raw_value = text
                    if "_" in raw_value:
                        raw_value = raw_value.split("_", 1)[-1]
                    await save_answer(chat_id, field, raw_value)
                else:
                    await save_answer(chat_id, field, text)
                return await ask_next(chat_id)

        # Si ya no está en onboarding, (en el paso 2 implementaremos menú principal)
        return await tg("sendMessage", {"chat_id": chat_id, "text": "Perfil ya configurado. (Próximo paso: menú principal) Usa /start para reiniciar."})

    # fuera de flujo
    return await tg("sendMessage", {"chat_id": chat_id, "text": "No entiendo ese comando. Usa /start para comenzar."})
