import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, UniqueConstraint, Float, Text
from sqlalchemy.orm import relationship
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    avatar = Column(String, nullable=True)

    tableros = relationship("Tablero", back_populates="propietario", cascade="all, delete-orphan")
    metas = relationship("MetaDB", back_populates="usuario", cascade="all, delete-orphan")
    habitos = relationship("Habito", back_populates="usuario", cascade="all, delete-orphan")
    transacciones = relationship("Transaccion", back_populates="usuario", cascade="all, delete-orphan")
    notas = relationship("Nota", back_populates="usuario", cascade="all, delete-orphan")
    deseos = relationship("Deseo", back_populates="usuario", cascade="all, delete-orphan")

class Tablero(Base):
    __tablename__ = "tableros"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    descripcion = Column(String, nullable=True)
    propietario_id = Column(Integer, ForeignKey("usuarios.id"))

    propietario = relationship("Usuario", back_populates="tableros")
    metas = relationship("MetaDB", back_populates="tablero", cascade="all, delete-orphan")
    habitos = relationship("Habito", back_populates="tablero", cascade="all, delete-orphan")

class MetaDB(Base):
    __tablename__ = "metas"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String)
    descripcion = Column(String, nullable=True)
    completada = Column(Boolean, default=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tablero_id = Column(Integer, ForeignKey("tableros.id"))

    usuario = relationship("Usuario", back_populates="metas")
    tablero = relationship("Tablero", back_populates="metas")

class Habito(Base):
    __tablename__ = "habitos"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    icono = Column(String, default="🌱")
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tablero_id = Column(Integer, ForeignKey("tableros.id"))

    usuario = relationship("Usuario", back_populates="habitos")
    tablero = relationship("Tablero", back_populates="habitos")
    registros = relationship("RegistroHabito", back_populates="habito", cascade="all, delete-orphan")

class RegistroHabito(Base):
    __tablename__ = "registros_habitos"
    id = Column(Integer, primary_key=True, index=True)
    habito_id = Column(Integer, ForeignKey("habitos.id"))
    fecha = Column(Date, default=datetime.date.today)
    completado = Column(Boolean, default=True)
    habito = relationship("Habito", back_populates="registros")
    __table_args__ = (UniqueConstraint('habito_id', 'fecha', name='uq_habito_fecha'),)

# MODULOS GLOBALES (Sin tablero_id)
class Transaccion(Base):
    __tablename__ = "transacciones"
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    concepto = Column(String, nullable=False)
    categoria = Column(String, default="General")
    fecha = Column(Date, default=datetime.date.today)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="transacciones")

class Nota(Base):
    __tablename__ = "notas"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    contenido = Column(Text, nullable=True)
    fecha_creacion = Column(Date, default=datetime.date.today)
    fecha_actualizacion = Column(Date, default=datetime.date.today, onupdate=datetime.date.today)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="notas")

class Deseo(Base):
    __tablename__ = "deseos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    url = Column(String, nullable=True)
    imagen = Column(String, nullable=True) # NUEVO: Imagen del producto
    comprado = Column(Boolean, default=False)
    fecha_creacion = Column(Date, default=datetime.date.today)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="deseos")