"""
Multi-Tenant Authentication & Authorization System

- JWT-based session tokens (24h expiry)
- bcrypt password hashing
- Tenant isolation: each user sees only their own data
- admin role (frank) sees everything
- No signup — accounts are hardcoded
"""

import os
import time
import hmac
import hashlib
import secrets
import logging
from typing import Optional
from datetime import datetime, timedelta

import jwt
import bcrypt

logger = logging.getLogger("ai_os.auth")

# ─── Secret key (generated once, stored in env or file) ───
_AUTH_SECRET_FILE = os.path.join(os.path.expanduser("~"), ".aios_auth_secret")

def _get_secret() -> str:
    if os.path.exists(_AUTH_SECRET_FILE):
        with open(_AUTH_SECRET_FILE, "r") as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    os.makedirs(os.path.dirname(_AUTH_SECRET_FILE), exist_ok=True)
    with open(_AUTH_SECRET_FILE, "w") as f:
        f.write(secret)
    os.chmod(_AUTH_SECRET_FILE, 0o600)
    return secret

SECRET_KEY = _get_secret()
ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

# ─── User Database (hardcoded, hashed) ───
# Passwords hashed with bcrypt at import time
def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")

class TenantUser:
    def __init__(self, username: str, password_hash: str, display_name: str, role: str, tenant_id: str, allowed_datasets: list[str]):
        self.username = username
        self.password_hash = password_hash
        self.display_name = display_name
        self.role = role  # "admin" or "user"
        self.tenant_id = tenant_id
        self.allowed_datasets = allowed_datasets  # dataset prefixes this user can see

USERS: dict[str, TenantUser] = {}

def _init_users():
    global USERS
    USERS = {
        "baguley": TenantUser(
            username="baguley",
            password_hash=_hash_password("Frankie578"),
            display_name="Baguley Limited",
            role="user",
            tenant_id="baguley",
            allowed_datasets=["baguley_limited", "regions"],
        ),
        "geologist": TenantUser(
            username="geologist",
            password_hash=_hash_password("Frankie001"),
            display_name="Geologist",
            role="user",
            tenant_id="geologist",
            allowed_datasets=["geology", "soil", "mining", "satellite"],
        ),
        "frank": TenantUser(
            username="frank",
            password_hash=_hash_password("voldemort578"),
            display_name="Frank (Admin)",
            role="admin",
            tenant_id="frank",
            allowed_datasets=["*"],  # admin sees everything
        ),
    }

_init_users()

# ─── JWT Operations ───

def create_token(username: str) -> str:
    user = USERS.get(username)
    if not user:
        raise ValueError("Unknown user")
    payload = {
        "sub": user.username,
        "role": user.role,
        "tid": user.tenant_id,
        "display": user.display_name,
        "iat": int(time.time()),
        "exp": int(time.time()) + (TOKEN_EXPIRY_HOURS * 3600),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    """Returns payload dict if valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Check expiry explicitly (belt and suspenders)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def authenticate(username: str, password: str) -> Optional[str]:
    """Returns JWT token string if valid, None otherwise. No signup."""
    user = USERS.get(username)
    if not user:
        # Constant-time comparison even for unknown users to prevent timing attacks
        bcrypt.checkpw(b"dummy", bcrypt.gensalt())
        logger.warning(f"Failed login attempt for unknown user: {username}")
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        logger.warning(f"Failed login attempt for user: {username}")
        return None
    logger.info(f"Successful login: {username} (role={user.role}, tenant={user.tenant_id})")
    return create_token(username)

def get_user(token_payload: dict) -> Optional[TenantUser]:
    username = token_payload.get("sub")
    return USERS.get(username)

# ─── Authorization Helpers ───

def is_admin(payload: dict) -> bool:
    return payload.get("role") == "admin"

def can_access_dataset(payload: dict, dataset_path: str) -> bool:
    """Check if the user can access a specific dataset file."""
    user = USERS.get(payload.get("sub", ""))
    if not user:
        return False
    if "*" in user.allowed_datasets:
        return True
    for prefix in user.allowed_datasets:
        if dataset_path.startswith(prefix):
            return True
    return False

def get_tenant_id(payload: dict) -> str:
    return payload.get("tid", "unknown")
