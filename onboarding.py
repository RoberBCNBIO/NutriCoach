# onboarding.py

import json
from db import SessionLocal, User
from telegram_utils import tg   # limpio, sin import circular

# ---------- utilidades de listas ----------
def load_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        v = json.loads(value)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return [s.strip() for s in str(value).split(",") if s.strip()]

def dump_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)

def toggle_item(items: list[str], item: str) -> list[str]:
    if item in items:
        return [x for x in items if x != item]
    return items + [item]

# ---------- teclados ----------
def kb_sexo():
    return {"inline_keyboard":[
        [{"text":"Masculino","callback_data":"sexo_M"},
         {"text":"Femenino","callback_data":"sexo_F"},
         {"text":"Prefiero no decir","callback_data":"sexo_ND"}]
    ]}

def kb_actividad():
    return {"inline_keyboard":[
        [{"text":"Sedentario","callback_data":"act_sedentario"}],
        [{"text":"Ligero","callback_data":"act_ligero"}],
        [{"text":"Moderado","callback_data":"act_moderado"}],
        [{"text":"Alto","callback_data":"act_alto"}],
        [{"text":"Muy alto","callback_data":"act_muy_alto"}]
    ]}

def kb_reset_confirm():
    return {"inline_keyboard":[
        [{"text":"✅ Sí, sobrescribir","callback_data":"reset_yes"}],
        [{"text":"❌ No, mantener perfil","callback_data":"reset_no"}]
    ]}

def kb_main_menu():
    return {"inline_keyboard":[
        [{"text":"📅 Generar dieta completa","callback_data":"menu_generate"}],
        [{"text":"🛒 Lista de la compra","callback_data":"menu_shopping"}],
        [{"text":"ℹ️ Ver mi perfil","callback_data":"menu_profile"}],
        [{"text":"💬 Chat con coach","callback_data":"menu_chat"}],
        [{"text":"❓ Ayuda","callback_data":"menu_help"}]
    ]}

# ---------- flujo ----------
async def start_onboarding(chat_id: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            u = User(chat_id=str(chat_id), onboarding_step=1)
            s.add(u)
            s.commit()
    await tg("sendMessage", {
        "chat_id": chat_id,
        "text": "¡Hola! Soy tu coach nutricional 🤖🥗. Vamos a configurar tu perfil paso a paso.\n\nPrimero: ¿Cuál es tu sexo?",
        "reply_markup": kb_sexo()
    })

async def ask_next(chat_id: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return await start_onboarding(chat_id)

        step = u.onboarding_step or 1

        if step == 1 and not u.sexo:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu sexo?", "reply_markup": kb_sexo()})
        if step == 2 and not u.edad:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué edad tienes? (solo número)"})
        if step == 3 and not u.altura_cm:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu altura en cm? (solo número)"})
        if step == 4 and not u.peso_kg:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu peso actual en kg? (puede ser decimal)"})
        if step == 5 and not u.actividad:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué nivel de actividad tienes?", "reply_markup": kb_actividad()})
        if step == 6 and not u.objetivo_detallado:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🎯 ¿Cuál es tu objetivo principal?"})
        if step == 7 and not u.estilo_dieta:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🍽️ ¿Qué estilo de cocina prefieres?"})
        if step == 8 and not u.preferencias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué alimentos prefieres incluir en tu dieta?"})
        if step == 9 and not u.no_gustos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué alimentos no te gustan o quieres evitar?"})
        if step == 10 and not u.alergias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Tienes alguna alergia o intolerancia?"})
        if step == 11 and not u.vetos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Hay algún alimento o grupo que quieras vetar por completo?"})
        if step == 12 and not u.tiempo_cocina:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "⏱️ ¿Cuánto tiempo tienes para cocinar normalmente? (ej: 15, 30, 45)"})
        if step == 13 and not u.equipamiento:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🔧 ¿Qué equipamiento tienes en tu cocina?"})
        if step == 14 and not u.duracion_plan_semanas:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuántas semanas quieres que dure tu plan? (solo número)"})
        if step == 15 and not u.pais:
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "🌍 ¿En qué país vives? Esto servirá para ajustar recetas e ingredientes a lo que normalmente encuentras en los supermercados de tu zona."
            })

        # Perfil completo
        u.onboarding_step = 0
        s.commit()
    await tg("sendMessage", {
        "chat_id": chat_id,
        "text": "🎉 ¡Perfil completo! Ahora puedes usar el menú principal:",
        "reply_markup": kb_main_menu()
    })

async def save_answer(chat_id: str, field: str, value: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return
        setattr(u, field, value)
        if u.onboarding_step and u.onboarding_step < 15:
            u.onboarding_step += 1
        else:
            u.onboarding_step = 0
        s.commit()
