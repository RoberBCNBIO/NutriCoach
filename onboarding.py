# onboarding.py

from db import SessionLocal, User
from telegram_utils import tg   # limpio, sin circular import


# --- Teclados de opciones ---
def kb_sexo():
    return {"inline_keyboard": [
        [{"text": "Masculino", "callback_data": "sexo_M"},
         {"text": "Femenino", "callback_data": "sexo_F"},
         {"text": "Prefiero no decir", "callback_data": "sexo_ND"}]
    ]}


def kb_actividad():
    return {"inline_keyboard": [
        [{"text": "Sedentario", "callback_data": "actividad_sedentario"}],
        [{"text": "Ligero", "callback_data": "actividad_ligero"}],
        [{"text": "Moderado", "callback_data": "actividad_moderado"}],
        [{"text": "Alto", "callback_data": "actividad_alto"}],
        [{"text": "Muy alto", "callback_data": "actividad_muy_alto"}]
    ]}


def kb_objetivo_detallado():
    return {"inline_keyboard": [
        [{"text": "Perder grasa", "callback_data": "objetivo_perder_grasa"}],
        [{"text": "Ganar músculo", "callback_data": "objetivo_ganar_musculo"}],
        [{"text": "Definir abdomen", "callback_data": "objetivo_abdomen"}],
        [{"text": "Mente tranquila", "callback_data": "objetivo_mente"}],
        [{"text": "Desinflamar", "callback_data": "objetivo_desinflamar"}],
        [{"text": "Mejorar cardio", "callback_data": "objetivo_cardio"}],
        [{"text": "Subir energía", "callback_data": "objetivo_energia"}],
        [{"text": "Dormir mejor", "callback_data": "objetivo_sueno"}],
    ]}


def kb_estilo_dieta():
    return {"inline_keyboard": [
        [{"text": "Mediterránea 🍅", "callback_data": "dieta_mediterranea"}],
        [{"text": "Japonesa 🍣", "callback_data": "dieta_japonesa"}],
        [{"text": "Tailandesa 🌶️", "callback_data": "dieta_tailandesa"}],
        [{"text": "Árabe 🥙", "callback_data": "dieta_arabe"}],
        [{"text": "Vegana 🌱", "callback_data": "dieta_vegana"}],
        [{"text": "Americana 🍔", "callback_data": "dieta_americana"}],
    ]}


def kb_tiempo_cocina():
    return {"inline_keyboard": [
        [{"text": "≤15 min", "callback_data": "tiempo_15"}],
        [{"text": "~30 min", "callback_data": "tiempo_30"}],
        [{"text": ">45 min", "callback_data": "tiempo_45"}],
    ]}


def kb_equipamiento():
    return {"inline_keyboard": [
        [{"text": "Airfryer 🍟", "callback_data": "equip_airfryer"}],
        [{"text": "Horno 🔥", "callback_data": "equip_horno"}],
        [{"text": "Microondas ⚡", "callback_data": "equip_micro"}],
        [{"text": "Thermomix 🥘", "callback_data": "equip_thermo"}],
        [{"text": "Ninguno", "callback_data": "equip_none"}],
    ]}


# --- Guardar respuesta y avanzar ---
async def save_answer(chat_id: str, field: str, value: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return
        setattr(u, field, value)
        u.onboarding_step += 1
        s.commit()


# --- Inicio del onboarding ---
async def start_onboarding(chat_id: str):
    """Primer contacto de configuración"""
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


# --- Flujo de preguntas ---
async def ask_next(chat_id: str):
    """Decide la siguiente pregunta según el step"""
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
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu objetivo principal?", "reply_markup": kb_objetivo_detallado()})

        if step == 7 and not u.estilo_dieta:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué estilo de dieta prefieres?", "reply_markup": kb_estilo_dieta()})

        if step == 8 and not u.preferencias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🍴 ¿Qué comidas te gustan especialmente?"})

        if step == 9 and not u.no_gustos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "❌ ¿Qué alimentos no te gustan o quieres evitar?"})

        if step == 10 and not u.alergias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ ¿Tienes alguna alergia o intolerancia?"})

        if step == 11 and not u.vetos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🚫 ¿Hay alimentos que quieras prohibir totalmente?"})

        if step == 12 and not u.tiempo_cocina:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "⌛ ¿Cuánto tiempo tienes para cocinar normalmente?", "reply_markup": kb_tiempo_cocina()})

        if step == 13 and not u.equipamiento:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🍳 ¿Qué equipamiento tienes?", "reply_markup": kb_equipamiento()})

        if step == 14 and not u.duracion_plan_semanas:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "📅 ¿Cuántas semanas quieres que dure tu plan?"})

        if step == 15 and not u.pais:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🌍 ¿En qué país estás?"})

        # Si llega aquí, está completo
        u.onboarding_step = 0
        s.commit()

    await tg("sendMessage", {
        "chat_id": chat_id,
        "text": "🎉 ¡Perfil completo! Ya puedes ver tu plan actual, generar tu dieta y registrar tu progreso."
    })
