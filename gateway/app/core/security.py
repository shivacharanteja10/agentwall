"""Security utilities: API key hashing, JWT tokens, password hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import get_settings
from jose import jwt
from passlib.context import CryptContext

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return pwd_context.hash(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return pwd_context.verify(plain_key, hashed_key)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"aw_{secrets.token_urlsafe(32)}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.JWTError:
        return None


def hash_request(request_data: dict) -> str:
    """Create a SHA256 hash of the request data for audit chaining."""
    import json
    canonical = json.dumps(request_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_chain_hash(current_hash: str, previous_hash: Optional[str]) -> str:
    """Compute the chained hash for audit log integrity."""
    if previous_hash is None:
        return current_hash
    combined = f"{previous_hash}:{current_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()
