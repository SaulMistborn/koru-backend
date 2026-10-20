import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Lee la URL secreta desde Render. Si estás en tu compu, usa la local.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:contraseña@localhost:5432/koru_db")

# Configuración con pool_pre_ping para mantener la conexión viva con Neon
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()