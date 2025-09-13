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
    # fallback por si alguien guardó texto plano separado por comas
    return [s.strip() for s in str(value).split(",") if s.strip()]

def dump_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)

def toggle_item(items: list[str], item: str) -> list[str]:
    if item in items:
        return [x for x in items if x != item]
    return items + [item]

# ---------- teclados de selección simple (existentes) ----------
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

# ---------- teclados de MULTIselección con toggle + continuar ----------
OBJ_OPTS = [
    ("Perder grasa", "grasa"),
    ("Ganar músculo", "musculo"),
    ("Definir abdomen", "abdomen"),
    ("Mente tranquila", "mente"),
    ("Desinflamar", "keto"),
    ("Mejorar cardio", "cardio"),
    ("Subir energía", "energia"),
    ("Dormir mejor", "sueno"),
]

def kb_objetivo_multiselect(selected: list[str]):
    rows = []
    for label, key in OBJ_OPTS:
        chosen = "✅ " + label if key in selected else label
        rows.append([{"text": chosen, "callback_data": f"obj_toggle_{key}"}])
    rows.append([{"text":"Continuar ➡️","callback_data":"obj_done"}])
    return {"inline_keyboard": rows}

DIET_OPTS = [
    ("Mediterránea 🍅", "mediterranea"),
    ("Japonesa 🍣", "japonesa"),
    ("Tailandesa 🌶️", "tailandesa"),
    ("Árabe 🥙", "arabe"),
    ("Vegana 🌱", "vegana"),
    ("Americana 🍔", "americana"),
]

def kb_estilo_multiselect(selected: list[str]):
    rows = []
    for label, key in DIET_OPTS:
        chosen = "✅ " + label if key in selected else label
        rows.append([{"text": chosen, "callback_data": f"diet_toggle_{key}"}])
    rows.append([{"text":"Continuar ➡️","callback_data":"diet_done"}])
    return {"inline_keyboard": rows}

EQUIP_OPTS = [
    ("Airfryer 🍟", "airfryer"),
    ("Horno 🔥", "horno"),
    ("Microondas ⚡", "micro"),
    ("Thermomix 🥘", "thermo"),
    ("Ninguno", "none"),
]

def kb_equip_multiselect(selected: list[str]):
    rows = []
    for label, key in EQUIP_OPTS:
        chosen = "✅ " + label if key in selected else label
        rows.append([{"text": chosen, "callback_data": f"equip_toggle_{key}"}])
    rows.append([{"text":"Continuar ➡️","callback_data":"equip_done"}])
    return {"inline_keyboard": rows}

# ---------- teclado confirmación reset ----------
def kb_reset_confirm():
    return {"inline_keyboard":[
        [{"text":"✅ Sí, sobrescribir","callback_data":"reset_yes"}],
        [{"text":"❌ No, mantener perfil","callback_data":"reset_no"}]
    ]}

# ---------- flujo ----------
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

        # ---- MULTI: OBJETIVO ----
        if step == 6:
            sel = load_list(u.objetivo_detallado)
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "🎯 ¿Cuál es tu objetivo principal? (puedes elegir varias opciones y luego pulsa *Continuar*)",
                "reply_markup": kb_objetivo_multiselect(sel)
            })

        # ---- MULTI: ESTILO/DIETA ----
        if step == 7:
            sel = load_list(u.estilo_dieta)
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "🍽️ ¿Qué estilos de cocina prefieres? (elige varias y pulsa *Continuar*)",
                "reply_markup": kb_estilo_multiselect(sel)
            })

        if step == 8 and not u.preferencias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué alimentos prefieres incluir en tu dieta?"})

        if step == 9 and not u.no_gustos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Qué alimentos no te gustan o quieres evitar?"})

        if step == 10 and not u.alergias:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Tienes alguna alergia o intolerancia?"})

        if step == 11 and not u.vetos:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Hay algún alimento o grupo que quieras vetar por completo?"})

        if step == 12 and not u.tiempo_cocina:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuánto tiempo tienes para cocinar normalmente? (usa los botones)", 
                                            "reply_markup": {
                                                "inline_keyboard":[
                                                    [{"text":"≤15 min","callback_data":"cook_15"}],
                                                    [{"text":"~30 min","callback_data":"cook_30"}],
                                                    [{"text":">45 min","callback_data":"cook_45"}]
                                                ]
                                            }})

        # ---- MULTI: EQUIPAMIENTO ----
        if step == 13:
            sel = load_list(u.equipamiento)
            return await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "🔧 ¿Qué equipamiento tienes? (elige varias y pulsa *Continuar*)",
                "reply_markup": kb_equip_multiselect(sel)
            })

        if step == 14 and not u.duracion_plan_semanas:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿Cuántas semanas quieres que dure tu plan? (solo número)"})

        if step == 15 and not u.pais:
            return await tg("sendMessage", {"chat_id": chat_id, "text": "¿En qué país vives? (sirve para ajustar recetas e ingredientes)"} )

        # Si llega aquí, está completo
        u.onboarding_step = 0
        s.commit()
    await tg("sendMessage", {"chat_id": chat_id, "text": "🎉 ¡Perfil completo! Ya puedes ver tu plan actual, generar tu dieta y registrar tu progreso."})

# ---------- guardar respuestas ----------
async def save_answer(chat_id: str, field: str, value: str):
    """Guarda la respuesta en la DB y avanza al siguiente step (para campos de 1 valor)"""
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

async def save_list_toggle(chat_id: str, field: str, item_key: str):
    """Alterna un item en un campo de lista (no avanza de step)"""
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return
        current = load_list(getattr(u, field))
        updated = toggle_item(current, item_key)
        setattr(u, field, dump_list(updated))
        s.commit()

async def advance_step(chat_id: str):
    """Avanza manualmente el step (para cuando se pulsa Continuar en multiselect)"""
    with SessionLocal() as s:
        u = s.query(User).filter(User.chat_id == str(chat_id)).first()
        if not u:
            return
        if u.onboarding_step and u.onboarding_step < 15:
            u.onboarding_step += 1
        else:
            u.onboarding_step = 0
        s.commit()
