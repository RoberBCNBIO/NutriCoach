from dataclasses import dataclass
from typing import Literal, Dict, Any

Actividad = Literal["sedentaria","ligera","moderada","alta","muy alta"]

FACTORES = {
    "sedentaria": 1.2,
    "ligera": 1.375,
    "moderada": 1.55,
    "alta": 1.725,
    "muy alta": 1.9,
}

@dataclass
class Profile:
    nombre: str
    sexo: Literal["M","F"]
    edad: int
    altura_cm: int
    peso_kg: float
    actividad: Actividad = "ligera"
    objetivo: Literal["perder","mantener","ganar"] = "perder"
    alergias: list[str] = None
    vetos: list[str] = None
    equipamiento: list[str] = None
    tiempo_min: int = 20
    pais: str = "ES"

def mifflin_st_jeor(sexo: str, kg: float, cm: int, edad: int) -> float:
    return 10*kg + 6.25*cm - 5*edad + (5 if sexo.upper()=="M" else -161)

def tdee(bmr: float, actividad: Actividad) -> float:
    return bmr * FACTORES.get(actividad, 1.375)

def objetivo_kcal(tdee_val: float, objetivo: str) -> float:
    if objetivo == "perder":
        return tdee_val * 0.85
    if objetivo == "ganar":
        return tdee_val * 1.10
    return tdee_val

def calcular_macros(peso_kg: float, kcal_obj: float) -> dict:
    # bandas seguras
    prote = max(min(2.2*peso_kg, 180), 1.6*peso_kg)
    grasa = max(0.8*peso_kg, 40)
    kcal_prot = prote*4
    kcal_grasa = grasa*9
    carb = max((kcal_obj - kcal_prot - kcal_grasa)/4, 0)
    return {
        "kcal": round(kcal_obj),
        "prote_g": round(prote),
        "grasa_g": round(grasa),
        "carbo_g": round(carb)
    }

def plantilla_plan_dia(kcal: int) -> Dict[str, Any]:
    # Simplificado – luego lo conectaremos a recipes.json
    return {
        "desayuno": "Yogur griego + fruta + avena (~400 kcal)",
        "comida": "Pollo adobado air fryer + patata y calabacín (~700 kcal)",
        "cena": "Tortilla + ensalada + pan integral (~600 kcal)",
        "snack": "Fruta o skyr (~200 kcal)",
        "kcal_approx": kcal
    }
