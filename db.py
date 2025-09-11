from sqlalchemy import Column, Integer, String, Float, Text, Date, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, index=True)

    nombre = Column(String, nullable=True)
    sexo = Column(String, nullable=True)            # "M" / "F"
    edad = Column(Integer, nullable=True)
    altura_cm = Column(Integer, nullable=True)
    peso_kg = Column(Float, nullable=True)

    actividad = Column(String, default="ligera")
    objetivo = Column(String, default="perder")     # perder/mantener/ganar
    alergias = Column(Text, default="")
    vetos = Column(Text, default="")
    equipamiento = Column(Text, default="")
    tiempo_min = Column(Integer, default=20)
    pais = Column(String, default="ES")

class CheckIn(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    fecha = Column(Date, server_default=func.current_date())
    hambre = Column(Integer)        # 1-5
    energia = Column(Integer)       # 1-5
    adhesion = Column(Integer)      # 0-100
    peso_kg = Column(Float, nullable=True)
    notas = Column(Text, default="")

class MenuLog(Base):
    __tablename__ = "menulogs"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True)
    params = Column(JSON)           # ej. {"kcal": 1900}
    menu_json = Column(JSON)        # menú generado (3 días)

# SQLite local (archivo en la carpeta del proyecto)
engine = create_engine("sqlite:///./nutricoach.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    Base.metadata.create_all(engine)
