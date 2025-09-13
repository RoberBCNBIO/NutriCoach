# db.py

import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Configuración base
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://user:password@localhost:5432/dietabot")

Base = declarative_base()


# ---------- MODELOS ----------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, unique=True, index=True)

    nombre = Column(String, nullable=True)
    sexo = Column(String, nullable=True)
    edad = Column(Integer, nullable=True)
    altura_cm = Column(Float, nullable=True)
    peso_kg = Column(Float, nullable=True)
    actividad = Column(String, nullable=True)
    objetivo_detallado = Column(String, nullable=True)
    estilo_dieta = Column(String, nullable=True)
    preferencias = Column(String, nullable=True)
    no_gustos = Column(String, nullable=True)
    alergias = Column(String, nullable=True)
    vetos = Column(String, nullable=True)
    tiempo_cocina = Column(String, nullable=True)
    equipamiento = Column(String, nullable=True)
    duracion_plan_semanas = Column(Integer, nullable=True)
    semana_actual = Column(Integer, default=1)
    kcal_objetivo = Column(Integer, nullable=True)
    macros = Column(String, nullable=True)         # JSON como texto
    menu_activo = Column(String, nullable=True)    # JSON como texto
    onboarding_step = Column(Integer, default=1)
    pais = Column(String, nullable=True)


class MenuLog(Base):
    __tablename__ = "menulogs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, index=True)
    params = Column(String, nullable=True)       # JSON de parámetros como texto
    menu_json = Column(String, nullable=True)    # JSON del menú como texto
    timestamp = Column(DateTime, default=datetime.utcnow)


# ---------- CONEXIÓN ----------
engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
