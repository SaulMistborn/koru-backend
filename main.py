from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import extract
from pydantic import BaseModel
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup

import models
import auth
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Koru API")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


# -------------------------------------------------------------
# ESQUEMAS PYDANTIC
# -------------------------------------------------------------
class UsuarioCreate(BaseModel): nombre: str; email: str; password: str


class UsuarioResponse(BaseModel):
    id: int;
    nombre: str;
    email: str

    class Config: from_attributes = True


class LoginRequest(BaseModel): email: str; password: str


class TableroCreate(BaseModel): nombre: str; descripcion: Optional[str] = None


class TableroResponse(BaseModel):
    id: int;
    nombre: str;
    descripcion: Optional[str];
    propietario_id: int

    class Config: from_attributes = True


class MetaCreate(BaseModel): titulo: str; descripcion: Optional[str] = None; tablero_id: int


class MetaResponse(BaseModel):
    id: int;
    titulo: str;
    descripcion: Optional[str];
    completada: bool;
    tablero_id: int

    class Config: from_attributes = True


class HabitoCreate(BaseModel): titulo: str; icono: Optional[str] = "🌱"; tablero_id: int


class HabitoResponse(BaseModel):
    id: int;
    titulo: str;
    icono: str;
    tablero_id: int;
    completado_hoy: bool;
    racha_actual: int;
    ultimos_7_dias: List[str]

    class Config: from_attributes = True


class TransaccionCreate(BaseModel): tipo: str; monto: float; concepto: str; categoria: Optional[str] = "General"; fecha: \
Optional[date] = None


class TransaccionResponse(BaseModel):
    id: int;
    tipo: str;
    monto: float;
    concepto: str;
    categoria: str;
    fecha: date

    class Config: from_attributes = True


class NotaCreate(BaseModel): titulo: str; contenido: Optional[str] = ""


class NotaUpdate(BaseModel): titulo: Optional[str] = None; contenido: Optional[str] = None


class NotaResponse(BaseModel):
    id: int;
    titulo: str;
    contenido: Optional[str];
    fecha_creacion: date;
    fecha_actualizacion: date

    class Config: from_attributes = True


class PerfilStatsResponse(BaseModel):
    nombre: str;
    email: str;
    avatar: Optional[str] = None;
    total_cuadernos: int;
    metas_completadas: int;
    habitos_activos: int;
    racha_global: int;
    nivel: int

    class Config: from_attributes = True


class UpdateAvatarRequest(BaseModel): avatar_url: str


class DeseoCreate(BaseModel): nombre: str; precio: float; url: Optional[str] = None; imagen: Optional[str] = None


class DeseoResponse(BaseModel):
    id: int;
    nombre: str;
    precio: float;
    url: Optional[str];
    imagen: Optional[str];
    comprado: bool;
    fecha_creacion: date

    class Config: from_attributes = True


class ScrapeRequest(BaseModel): url: str


def procesar_habito_dto(habito: models.Habito) -> dict:
    hoy = date.today()
    fechas_completadas = {r.fecha for r in habito.registros if r.completado}
    completado_hoy = hoy in fechas_completadas
    racha = 0
    dia_evaluado = hoy if completado_hoy else hoy - timedelta(days=1)
    while dia_evaluado in fechas_completadas:
        racha += 1;
        dia_evaluado -= timedelta(days=1)
    return {"id": habito.id, "titulo": habito.titulo, "icono": habito.icono, "tablero_id": habito.tablero_id,
            "completado_hoy": completado_hoy, "racha_actual": racha,
            "ultimos_7_dias": [r.fecha.isoformat() for r in habito.registros if r.completado]}


# -------------------------------------------------------------
# RUTAS BÁSICAS (Usuarios, Auth, Tableros, Metas, Hábitos)
# -------------------------------------------------------------
@app.post("/usuarios/", response_model=UsuarioResponse)
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first():
        raise HTTPException(status_code=400, detail="Este correo ya está registrado.")
    nuevo_usuario = models.Usuario(nombre=usuario.nombre, email=usuario.email,
                                   password_hash=auth.encriptar_password(usuario.password))
    db.add(nuevo_usuario);
    db.commit();
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@app.post("/login/")
def login(credenciales: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == credenciales.email).first()
    if not usuario or not auth.verificar_password(credenciales.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    token = auth.crear_token_acceso(datos={"sub": str(usuario.id), "email": usuario.email})
    return {"access_token": token, "token_type": "bearer",
            "usuario": {"id": usuario.id, "nombre": usuario.nombre, "email": usuario.email}}


@app.post("/tableros/", response_model=TableroResponse)
def crear_tablero(tablero: TableroCreate, db: Session = Depends(get_db),
                  usuario_id: int = Depends(auth.obtener_usuario_actual)):
    t = models.Tablero(nombre=tablero.nombre, descripcion=tablero.descripcion, propietario_id=usuario_id)
    db.add(t);
    db.commit();
    db.refresh(t);
    return t


@app.get("/tableros/", response_model=List[TableroResponse])
def obtener_tableros(db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    return db.query(models.Tablero).filter(models.Tablero.propietario_id == usuario_id).all()


@app.delete("/tableros/{tablero_id}")
def eliminar_tablero(tablero_id: int, db: Session = Depends(get_db),
                     usuario_id: int = Depends(auth.obtener_usuario_actual)):
    t = db.query(models.Tablero).filter(models.Tablero.id == tablero_id,
                                        models.Tablero.propietario_id == usuario_id).first()
    if not t: raise HTTPException(status_code=404)
    db.delete(t);
    db.commit();
    return {"mensaje": "Eliminado"}


@app.post("/metas/", response_model=MetaResponse)
def crear_meta(meta: MetaCreate, db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    m = models.MetaDB(titulo=meta.titulo, descripcion=meta.descripcion, tablero_id=meta.tablero_id,
                      usuario_id=usuario_id)
    db.add(m);
    db.commit();
    db.refresh(m);
    return m


@app.get("/metas/", response_model=List[MetaResponse])
def obtener_metas(tablero_id: int, db: Session = Depends(get_db),
                  usuario_id: int = Depends(auth.obtener_usuario_actual)):
    return db.query(models.MetaDB).filter(models.MetaDB.usuario_id == usuario_id,
                                          models.MetaDB.tablero_id == tablero_id).all()


@app.put("/metas/{meta_id}", response_model=MetaResponse)
def actualizar_meta(meta_id: int, db: Session = Depends(get_db),
                    usuario_id: int = Depends(auth.obtener_usuario_actual)):
    m = db.query(models.MetaDB).filter(models.MetaDB.id == meta_id, models.MetaDB.usuario_id == usuario_id).first()
    m.completada = not m.completada;
    db.commit();
    db.refresh(m);
    return m


@app.delete("/metas/{meta_id}")
def eliminar_meta(meta_id: int, db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    m = db.query(models.MetaDB).filter(models.MetaDB.id == meta_id, models.MetaDB.usuario_id == usuario_id).first()
    db.delete(m);
    db.commit();
    return {"mensaje": "Eliminada"}


@app.post("/habitos/", response_model=HabitoResponse)
def crear_habito(habito: HabitoCreate, db: Session = Depends(get_db),
                 usuario_id: int = Depends(auth.obtener_usuario_actual)):
    h = models.Habito(titulo=habito.titulo.strip(), icono=habito.icono or "🌱", tablero_id=habito.tablero_id,
                      usuario_id=usuario_id)
    db.add(h);
    db.commit();
    db.refresh(h);
    return procesar_habito_dto(h)


@app.get("/habitos/", response_model=List[HabitoResponse])
def obtener_habitos(tablero_id: int, db: Session = Depends(get_db),
                    usuario_id: int = Depends(auth.obtener_usuario_actual)):
    hs = db.query(models.Habito).filter(models.Habito.tablero_id == tablero_id,
                                        models.Habito.usuario_id == usuario_id).all()
    return [procesar_habito_dto(h) for h in hs]


@app.post("/habitos/{habito_id}/toggle", response_model=HabitoResponse)
def alternar_habito_hoy(habito_id: int, fecha: Optional[date] = None, db: Session = Depends(get_db),
                        usuario_id: int = Depends(auth.obtener_usuario_actual)):
    h = db.query(models.Habito).filter(models.Habito.id == habito_id, models.Habito.usuario_id == usuario_id).first()
    dia = fecha or date.today()
    reg = db.query(models.RegistroHabito).filter(models.RegistroHabito.habito_id == habito_id,
                                                 models.RegistroHabito.fecha == dia).first()
    if reg:
        db.delete(reg)
    else:
        db.add(models.RegistroHabito(habito_id=habito_id, fecha=dia, completado=True))
    db.commit();
    db.refresh(h);
    return procesar_habito_dto(h)


@app.delete("/habitos/{habito_id}")
def eliminar_habito(habito_id: int, db: Session = Depends(get_db),
                    usuario_id: int = Depends(auth.obtener_usuario_actual)):
    h = db.query(models.Habito).filter(models.Habito.id == habito_id, models.Habito.usuario_id == usuario_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hábito no encontrado")

    db.delete(h)
    db.commit()
    return {"mensaje": "Eliminado"}


# -------------------------------------------------------------
# MÓDULOS GLOBALES (Finanzas, Deseos, Notas)
# -------------------------------------------------------------
@app.post("/transacciones/", response_model=TransaccionResponse)
def crear_transaccion(transaccion: TransaccionCreate, db: Session = Depends(get_db),
                      usuario_id: int = Depends(auth.obtener_usuario_actual)):
    t = models.Transaccion(tipo=transaccion.tipo.lower(), monto=abs(transaccion.monto),
                           concepto=transaccion.concepto.strip(), categoria=transaccion.categoria,
                           fecha=transaccion.fecha or date.today(), usuario_id=usuario_id)
    db.add(t);
    db.commit();
    db.refresh(t);
    return t


@app.get("/transacciones/", response_model=List[TransaccionResponse])
def obtener_transacciones(mes: Optional[int] = None, anio: Optional[int] = None, db: Session = Depends(get_db),
                          usuario_id: int = Depends(auth.obtener_usuario_actual)):
    query = db.query(models.Transaccion).filter(models.Transaccion.usuario_id == usuario_id)
    if mes: query = query.filter(extract('month', models.Transaccion.fecha) == mes)
    if anio: query = query.filter(extract('year', models.Transaccion.fecha) == anio)
    return query.order_by(models.Transaccion.fecha.desc(), models.Transaccion.id.desc()).all()


@app.delete("/transacciones/{transaccion_id}")
def eliminar_transaccion(transaccion_id: int, db: Session = Depends(get_db),
                         usuario_id: int = Depends(auth.obtener_usuario_actual)):
    t = db.query(models.Transaccion).filter(models.Transaccion.id == transaccion_id,
                                            models.Transaccion.usuario_id == usuario_id).first()
    db.delete(t);
    db.commit();
    return {"mensaje": "Eliminada"}


@app.post("/deseos/", response_model=DeseoResponse)
def crear_deseo(deseo: DeseoCreate, db: Session = Depends(get_db),
                usuario_id: int = Depends(auth.obtener_usuario_actual)):
    d = models.Deseo(nombre=deseo.nombre.strip(), precio=abs(deseo.precio), url=deseo.url, imagen=deseo.imagen,
                     usuario_id=usuario_id)
    db.add(d);
    db.commit();
    db.refresh(d);
    return d


@app.get("/deseos/", response_model=List[DeseoResponse])
def obtener_deseos(db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    return db.query(models.Deseo).filter(models.Deseo.usuario_id == usuario_id).order_by(models.Deseo.comprado.asc(),
                                                                                         models.Deseo.id.desc()).all()


@app.post("/deseos/{deseo_id}/comprar")
def comprar_deseo(deseo_id: int, db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    deseo = db.query(models.Deseo).filter(models.Deseo.id == deseo_id, models.Deseo.usuario_id == usuario_id).first()
    deseo.comprado = True
    gasto = models.Transaccion(tipo="gasto", monto=deseo.precio, concepto=f"Meta lograda: {deseo.nombre}",
                               categoria="Deseos", fecha=date.today(), usuario_id=usuario_id)
    db.add(gasto);
    db.commit();
    db.refresh(deseo)
    return {"mensaje": "¡Felicidades por tu compra! El gasto se registró en tus finanzas."}


@app.delete("/deseos/{deseo_id}")
def eliminar_deseo(deseo_id: int, db: Session = Depends(get_db),
                   usuario_id: int = Depends(auth.obtener_usuario_actual)):
    d = db.query(models.Deseo).filter(models.Deseo.id == deseo_id, models.Deseo.usuario_id == usuario_id).first()
    db.delete(d);
    db.commit();
    return {"mensaje": "Deseo eliminado"}


@app.post("/notas/", response_model=NotaResponse)
def crear_nota(nota: NotaCreate, db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    n = models.Nota(titulo=nota.titulo.strip(), contenido=nota.contenido, usuario_id=usuario_id)
    db.add(n);
    db.commit();
    db.refresh(n);
    return n


@app.get("/notas/", response_model=List[NotaResponse])
def obtener_notas(db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    return db.query(models.Nota).filter(models.Nota.usuario_id == usuario_id).order_by(
        models.Nota.fecha_actualizacion.desc()).all()


@app.put("/notas/{nota_id}", response_model=NotaResponse)
def actualizar_nota(nota_id: int, nota_update: NotaUpdate, db: Session = Depends(get_db),
                    usuario_id: int = Depends(auth.obtener_usuario_actual)):
    n = db.query(models.Nota).filter(models.Nota.id == nota_id, models.Nota.usuario_id == usuario_id).first()
    if nota_update.titulo is not None: n.titulo = nota_update.titulo.strip()
    if nota_update.contenido is not None: n.contenido = nota_update.contenido
    db.commit();
    db.refresh(n);
    return n


@app.delete("/notas/{nota_id}")
def eliminar_nota(nota_id: int, db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    n = db.query(models.Nota).filter(models.Nota.id == nota_id, models.Nota.usuario_id == usuario_id).first()
    db.delete(n);
    db.commit();
    return {"mensaje": "Nota eliminada"}


# -------------------------------------------------------------
# HERRAMIENTAS ADICIONALES (Scraping y Perfil)
# -------------------------------------------------------------
import json


@app.post("/util/scrape")
def scrape_url(req: ScrapeRequest):
    url = req.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    # Headers robustos para engañar a las tiendas
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        session = requests.Session()
        res = session.get(url, headers=headers, timeout=10, allow_redirects=True)
        url_final = res.url
        soup = BeautifulSoup(res.text, 'html.parser')

        title = ""
        image = ""
        price = 0.0

        # --- 1. BUSCAR IMAGEN (Híbrido Amazon + General) ---
        if "amazon" in url_final.lower():
            amazon_img = soup.find(id="landingImage")
            if amazon_img and amazon_img.has_attr('src'):
                image = amazon_img['src']

        if not image:
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"): image = og_image["content"]

        # --- 2. BUSCAR TÍTULO (Híbrido Amazon + General) ---
        if "amazon" in url_final.lower():
            amazon_title = soup.find(id="productTitle")
            if amazon_title:
                title = amazon_title.text.strip()

        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]
            elif soup.title:
                title = soup.title.string

        # --- 3. BUSCAR PRECIO (JSON-LD, OpenGraph y Clases CSS) ---
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if "offers" in item and "price" in item["offers"]:
                            price = float(item["offers"]["price"])
                            break
                elif isinstance(data, dict):
                    if "offers" in data and "price" in data["offers"]:
                        if isinstance(data["offers"], list) and len(data["offers"]) > 0:
                            price = float(data["offers"][0].get("price", 0))
                        else:
                            price = float(data["offers"].get("price", 0))
                if price > 0: break
            except:
                pass

        if price == 0.0:
            price_tag = soup.find("meta", property="product:price:amount")
            if price_tag and price_tag.get("content"):
                try:
                    price = float(price_tag["content"])
                except:
                    pass

        if price == 0.0:
            for clase_precio in ["a-price-whole", "andes-money-amount__fraction", "price", "sale-price",
                                 "current-price"]:
                nodo = soup.find(class_=clase_precio)
                if nodo:
                    try:
                        texto = nodo.text.replace('$', '').replace(',', '').replace('MXN', '').strip()
                        if texto: price = float(texto)
                        break
                    except:
                        pass

        # Limpiar basurita del título
        if title:
            title = title.replace("Amazon.com.mx: ", "").replace("Mercado Libre", "").strip()

        return {
            "titulo": title[:150] if title else "",
            "imagen": image if image else "",
            "precio": price,
            "url_limpia": url_final
        }
    except Exception as e:
        print(f"Error scraping general: {e}")
        return {"titulo": "", "imagen": "", "precio": 0.0, "url_limpia": url}


@app.get("/perfil/stats", response_model=PerfilStatsResponse)
def obtener_estadisticas_perfil(db: Session = Depends(get_db), usuario_id: int = Depends(auth.obtener_usuario_actual)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    total_cuadernos = db.query(models.Tablero).filter(models.Tablero.propietario_id == usuario_id).count()
    metas_completadas = db.query(models.MetaDB).filter(models.MetaDB.usuario_id == usuario_id,
                                                       models.MetaDB.completada == True).count()
    habitos = db.query(models.Habito).filter(models.Habito.usuario_id == usuario_id).all()
    racha_global = max([procesar_habito_dto(h)["racha_actual"] for h in habitos] + [0])
    return {
        "nombre": usuario.nombre, "email": usuario.email, "avatar": usuario.avatar,
        "total_cuadernos": total_cuadernos, "metas_completadas": metas_completadas,
        "habitos_activos": len(habitos), "racha_global": racha_global,
        "nivel": 1 + (metas_completadas // 5) + (racha_global // 10)
    }


@app.post("/perfil/avatar")
def actualizar_avatar(request: UpdateAvatarRequest, db: Session = Depends(get_db),
                      usuario_id: int = Depends(auth.obtener_usuario_actual)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    usuario.avatar = request.avatar_url;
    db.commit();
    return {"mensaje": "Avatar actualizado"}