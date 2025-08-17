from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from models.user import User
from db.session import get_db
from sqlalchemy.orm import Session
from core.config import settings
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import logging

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with numeric exp claim."""
    to_encode = data.copy()
    if expires_delta:
        expire_dt = datetime.utcnow() + expires_delta
    else:
        expire_dt = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire_dt.timestamp())})
    token = jwt.encode(to_encode, str(settings.SECRET_KEY), algorithm=settings.ALGORITHM)
    return token


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Decode JWT, validate, and return the corresponding User from DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Verify signature and claims, but we'll check exp manually to allow small tolerance
        payload = jwt.decode(
            token,
            str(settings.SECRET_KEY),
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError as e:
        logging.warning(f"JWT decode failed: {e}")
        raise credentials_exception

    # Manual exp check with small tolerance
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        now = int(datetime.utcnow().timestamp())
        if exp < now - 10:
            logging.warning("JWT expired (exp=%s, now=%s)", exp, now)
            raise credentials_exception

    email = payload.get("sub")
    if not isinstance(email, str) or not email:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logging.warning("User not found for email from token: %s", email)
        raise credentials_exception
    return user
