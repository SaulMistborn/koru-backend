from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

SECRET_KEY = "tu_clave_secreta_super_segura_para_el_panel"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

def encriptar_password(password: str) -> str:
    # bcrypt requiere bytes y tiene límite de 72 bytes
    pwd_bytes = password.encode('utf-8')[:72]
    sal = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, sal).decode('utf-8')

def verificar_password(password_plano: str, password_encriptado: str) -> bool:
    pwd_bytes = password_plano.encode('utf-8')[:72]
    hash_bytes = password_encriptado.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hash_bytes)

def crear_token_acceso(datos: dict) -> str:
    datos_a_firmar = datos.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    datos_a_firmar.update({"exp": expiracion})
    return jwt.encode(datos_a_firmar, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> int:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: str = payload.get("sub")
        if usuario_id is None:
            raise credenciales_invalidas
        return int(usuario_id)
    except JWTError:
        raise credenciales_invalidas