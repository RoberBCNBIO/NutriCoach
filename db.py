import os
from sqlalchemy import Column, Integer, String, Float, Text, Date, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, index=True)

    # Datos básicos
    nombre = Column(String, nullable=True)
    sexo = Column(String, nullable=True)            # "M", "F", "ND"
    edad = Column(Integer, nullable=True)
    altura_cm = Column(Integer, nullable=True)
    peso_kg = Column(Float, nullable=True)
    actividad = Column(String, nullable=True)       # 🔹 Faltaba: sedentario, ligero, etc.

    # Plan nutricional
    objetivo_detallado = Column(String, default="perder grasa")  
    # ej: "perder grasa", "ganar músculo", "definir abdomen", "mente tranquila", "desinflamación"
    estilo_dieta = Column(String, default="mediterránea")  
    # ej: "mediterránea", "japonesa", "vegana"…
    preferencias = Column(Text, default="")         # comidas favoritas
    no_gustos = Column(Text, default="")            # comidas que no le gustan
    alergias = Column(Text, default="")
    vetos = Column(Text, default="")                # cosas que nunca quiere
    tiempo_cocina = Column(String, default="30min") # "<15", "30", ">45"
    equipamiento = Column(Text, default="")         # horno, airfryer, etc.

    # Plan activo
    duracion_plan_semanas = Column(Integer, default=8)
    semana_actual = Column(Integer, default=1)
    kcal_objetivo = Column(Integer, default=2000)
    macros = Column(JSON, default={})               # {proteinas, grasas, carbohidratos}
    menu_activo = Column(JSON, default={})          # calendario de dieta vigente

    # Seguimiento interno
    onboarding_step = Column(Integer, default=0)
    pais = Column(String, default="ES")


class CheckIn(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    fecha = Column(Date, server_default=func.current_date())
    hambre = Column(Integer)        # 1-5
    energia = Column(Integer)       # 1-5
    peso_kg = Column(Float, nullable=True)
    notas = Column(Text, default="")


class MenuLog(Base):
    __tablename__ = "menulogs"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    params = Column(JSON)           # ej. {"kcal": 1900}
    menu_json = Column(JSON)        # menú generado (3 días)


# --- Base de datos ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./nutricoach.db"  # fallback local
)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    """Crea las tablas en la base de datos si no existen."""
    Base.metadata.create_all(engine)
