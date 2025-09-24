# onboarding.py

import json
import re
from typing import Optional

from db import SessionLocal, User
from telegram_utils import tg  # limpio, sin import circular

# ---------- utils de saneo/parse ----------
NUM_ONLY_RE = re.compile(r"[^\d.,+-]")

def parse_int_safe(value: str, min_v: Optional[int] = None, max_v: Optional[int] = None) -> Optional[int]:
    if value is None:
        return None
    cleaned = NUM_ONLY_RE.sub("", str(value)).strip()
    cleaned = cleaned.replace(",", ".")
    try:
        num = float(cleaned)
        i = int(round(num))
        if min_v is not None and i < min_v:
            return None
        if max_v is not None and i > max_v:
            return None
        return i
    except Exception:
        return None

def parse_float_safe(value: str, min_v: Optional[float] = None, max_v: Optional[float] = None) -> Optional[float]:
    if value is None:
        return None
    cleaned = NUM_ONLY_RE.sub("", str(value)).strip()
    cleaned = cleaned.replace(",", ".")
    try:
        num = float(cleaned)
        if min_v is not None and num < min_v:
            return None
        if max_v is not None and num > max_v:
            return None
        return num
    except Exception:
        return None

def normalize_text(s: str) -> str:
    return (s or "").strip()

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
    return {
        "inline_keyboard": [
            [
                {"text": "Masculino", "callback_data": "sexo_M"},
                {"text": "Femenino", "callback_data": "sexo_F"},
                {"text": "Prefiero no decir", "callback_data": "sexo_ND"},
            ]
        ]
    }

def kb_actividad():
    return {
        "inline_keyboard": [
            [{"text": "Sedentario", "callback_data": "act_sedentario"}],
            [{"text": "Ligero", "callback_data": "act_ligero"}],
            [{"text": "Moderado", "callback_data": "act_moderado"}],
            [{"text": "Alto", "callback_data": "act_alto"}],
            [{"text": "Muy alto", "callback_data": "act_muy_alto"}],
        ]
    }

def kb_reset_confirm():
    return {
        "inline_keyboard": [
            [{"text": "✅ Sí, sobrescribir", "callback_data": "reset_yes"}],
            [{"text": "❌ No, mantener perfil", "callback_data": "reset_no"}],
        ]
    }

def kb_main_menu():
    return {
        "inline_keyboard": [
            [{"text": "📅 Generar dieta completa", "callback_data": "menu_generate"}],
            [{"text": "🛒 Lista de la compra", "callback_data": "menu_shopping"}],
            [{"text": "ℹ️ Ver mi perfil", "callback_data": "menu_profile"}],
            [{"text": "💬 Chat con coach", "callback_data": "menu_chat"}],
            [{"text": "❓ Ayuda", "callback_data": "menu_help"}],
        ]
    }

# ---------- helpers de flujo ----------
async def _profile_complete_message(chat_id: str):
    await tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "🎉 ¡Perfil completo! Ahora puedes usar el menú principal:",
            "reply_markup": kb_main_menu(),
        },
    )

async def _advance_and_ask_next(chat_id: str):
    # Relee estado y pregunta lo siguiente
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return await start_onboarding(chat_id)

        step = u.onboarding_step or 1

        if step == 1 and not u.sexo:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu sexo?", "reply_markup": kb_sexo()})
        if step == 2 and not u.edad:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué edad tienes? (solo número, ej. 35)"})
        if step == 3 and not u.altura_cm:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu altura en cm? (solo número, ej. 180)"})
        if step == 4 and not u.peso_kg:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuál es tu peso actual en kg? (puede ser decimal, ej. 72.5)"})
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
            return await tg("sendMessage", {"chat_id": chat_id, "text": "⏱️ ¿Cuánto tiempo tienes para cocinar normalmente? (minutos, ej. 30)"})
        if step == 13 and not u.equipamiento:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🔧 ¿Qué equipamiento tienes en tu cocina?"})
        if step == 14 and not u.duracion_plan_semanas:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuántas semanas quieres que dure tu plan? (solo número, ej. 4)"})
        if step == 15 and not u.pais:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "🌍 ¿En qué país vives?"})

        # Si nada bloquea, perfil listo
        u.onboarding_step = 0
        s.commit()

    await _profile_complete_message(chat_id)

def _bump_step(u: User, max_step: int = 15):
    if u.onboarding_step and u.onboarding_step < max_step:
        u.onboarding_step += 1
    else:
        u.onboarding_step = 0

# ---------- flujo público ----------
async def start_onboarding(chat_id: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            u = User(chat_id=str(chat_id), onboarding_step=1)
            s.add(u)
            s.commit()
    await tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "¡Hola! Soy tu coach nutricional 🤖🥗. Vamos a configurar tu perfil paso a paso.\n\nPrimero: ¿Cuál es tu sexo?",
            "reply_markup": kb_sexo(),
        },
    )

async def ask_next(chat_id: str):
    await _advance_and_ask_next(chat_id)

# Manejo de inline callbacks (sexo, actividad, y posibles confirmaciones)
async def handle_callback(chat_id: str, data: str):
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return await start_onboarding(chat_id)

        if data.startswith("sexo_"):
            code = data.split("_", 1)[1]
            mapping = {"M": "Masculino", "F": "Femenino", "ND": "No decir"}
            u.sexo = mapping.get(code, "No decir")
            if u.onboarding_step < 2:
                u.onboarding_step = 2
            s.commit()
            await tg("sendMessage", {"chat_id": chat_id, "text": f"Sexo: {u.sexo} ✅"})
            return await _advance_and_ask_next(chat_id)

        if data.startswith("act_"):
            act = data.split("_", 1)[1]
            u.actividad = act  # guardamos el literal (sedentario/ligero/moderado/alto/muy_alto)
            # si estamos en el paso 5, avanzamos
            if u.onboarding_step < 6:
                u.onboarding_step = 6
            s.commit()
            pretty = act.replace("_", " ").capitalize()
            await tg("sendMessage", {"chat_id": chat_id, "text": f"Actividad: {pretty} ✅"})
            return await _advance_and_ask_next(chat_id)

        # resets u otros
        if data == "reset_yes":
            # ejemplo sencillo: poner a 1 y borrar campos principales
            u.sexo = None
            u.edad = None
            u.altura_cm = None
            u.peso_kg = None
            u.actividad = None
            u.objetivo_detallado = None
            u.estilo_dieta = None
            u.preferencias = None
            u.no_gustos = None
            u.alergias = None
            u.vetos = None
            u.tiempo_cocina = None
            u.equipamiento = None
            u.duracion_plan_semanas = None
            u.pais = None
            u.onboarding_step = 1
            s.commit()
            await tg("sendMessage", {"chat_id": chat_id, "text": "✅ Perfil reiniciado. Empezamos de nuevo."})
            return await _advance_and_ask_next(chat_id)

        if data == "reset_no":
            return await tg("sendMessage", {"chat_id": chat_id, "text": "Perfecto, mantenemos tu perfil actual."})

# Guardado de respuestas de texto con validaciones
async def save_answer(chat_id: str, field: str, value: str):
    value = normalize_text(value)
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return

        # Validaciones según campo
        if field == "edad":
            i = parse_int_safe(value, min_v=5, max_v=100)
            if i is None:
                return await tg("sendMessage", {"chat_id": chat_id, "text": "Edad inválida. Escribe solo un número (ej. 35)."})
            u.edad = i
            if u.onboarding_step < 3:
                u.onboarding_step = 3

        elif field == "altura_cm":
            f = parse_float_safe(value, min_v=80, max_v=250)  # márgenes amplios
            if f is None:
                return await tg("sendMessage", {"chat_id": chat_id, "text": "Altura inválida. Introduce solo número en cm (ej. 180)."})
            u.altura_cm = f
            if u.onboarding_step < 4:
                u.onboarding_step = 4

        elif field == "peso_kg":
            f = parse_float_safe(value, min_v=20, max_v=400)
            if f is None:
                return await tg("sendMessage", {"chat_id": chat_id, "text": "Peso inválido. Introduce solo número en kg (ej. 72.5)."})
            u.peso_kg = f
            if u.onboarding_step < 5:
                u.onboarding_step = 5

        elif field == "objetivo_detallado":
            u.objetivo_detallado = value
            if u.onboarding_step < 7:
                u.onboarding_step = 7

        elif field == "estilo_dieta":
            u.estilo_dieta = value
            if u.onboarding_step < 8:
                u.onboarding_step = 8

        elif field == "preferencias":
            # dejamos texto libre; si algún día haces chips, puedes usar dump_list
            u.preferencias = value
            if u.onboarding_step < 9:
                u.onboarding_step = 9

        elif field == "no_gustos":
            u.no_gustos = value
            if u.onboarding_step < 10:
                u.onboarding_step = 10

        elif field == "alergias":
            u.alergias = value
            if u.onboarding_step < 11:
                u.onboarding_step = 11

        elif field == "vetos":
            u.vetos = value
            if u.onboarding_step < 12:
                u.onboarding_step = 12

        elif field == "tiempo_cocina":
            i = parse_int_safe(value, min_v=0, max_v=300)
            if i is None:
                return await tg("sendMessage", {"chat_id": chat_id, "text": "Tiempo inválido. Pon minutos en número (ej. 30)."})
            u.tiempo_cocina = str(i)  # tu modelo lo tiene como String
            if u.onboarding_step < 13:
                u.onboarding_step = 13

        elif field == "equipamiento":
            u.equipamiento = value
            if u.onboarding_step < 14:
                u.onboarding_step = 14

        elif field == "duracion_plan_semanas":
            i = parse_int_safe(value, min_v=1, max_v=52)
            if i is None:
                return await tg("sendMessage", {"chat_id": chat_id, "text": "Duración inválida. Pon semanas en número (1–52)."})
            u.duracion_plan_semanas = i
            if u.onboarding_step < 15:
                u.onboarding_step = 15

        elif field == "pais":
            u.pais = value
            u.onboarding_step = 0  # cierre

        elif field == "sexo":
            # Para completitud si llega por texto
            val = value.lower()
            if val.startswith("m"):
                u.sexo = "Masculino"
            elif val.startswith("f"):
                u.sexo = "Femenino"
            else:
                u.sexo = "No decir"
            if u.onboarding_step < 2:
                u.onboarding_step = 2

        elif field == "actividad":
            # Para completitud si llega por texto
            val = value.lower()
            opciones = ["sedentario", "ligero", "moderado", "alto", "muy alto", "muy_alto"]
            matched = None
            for o in opciones:
                if o.replace(" ", "_") in val:
                    matched = o.replace(" ", "_")
                    break
            u.actividad = matched or "sedentario"
            if u.onboarding_step < 6:
                u.onboarding_step = 6

        else:
            # Fallback genérico: guardamos como texto
            setattr(u, field, value)
            _bump_step(u)

        s.commit()

    # Pregunta el siguiente campo o cierra
    await _advance_and_ask_next(chat_id)
