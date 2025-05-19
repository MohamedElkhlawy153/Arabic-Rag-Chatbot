# backend/app/core/security.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from .config import settings  # Your existing settings import

# For future use if you store hashed passwords
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)
ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def verify_password(plain_password: str, stored_password: str) -> bool:
    """Verifies a plain password against a stored one."""
    # For hardcoded password in settings, direct comparison.
    # If stored_password was a hash from pwd_context.hash(plain_password):
    # return pwd_context.verify(plain_password, stored_password)
    return plain_password == stored_password


def get_password_hash(password: str) -> str:
    """Hashes a password for storage."""
    # return pwd_context.hash(password)
    # For now, if you were to hash the setting, you'd do it once.
    # This function isn't used with the hardcoded password setting directly.
    raise NotImplementedError("Password hashing should be used with DB-stored users.")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes an access token. Returns payload if valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Check for 'exp' (expiration) and 'sub' (subject/username)
        if "exp" not in payload or "sub" not in payload:
            return None

        return payload
    except JWTError:
        return None
