"""
Multi-Tenant Authentication & Authorization System

- JWT-based session tokens (24h expiry)
- bcrypt password hashing
- Tenant isolation: each user sees only their own data
- admin role (frank) sees everything
- Open signup with a fixed capacity (6 slots). Provisioned accounts persist
  on disk (bcrypt hash only, never plaintext). Once all slots are filled the
  sign-up page is automatically disabled server-side.
- Login accepts either a username or an email.
"""

import os
import time
import json
import secrets
import logging
from pathlib import Path
from typing import Optional

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

# ─── Base accounts (hardcoded). Signed-up team accounts are loaded from disk. ───
# geologist was removed and replaced by the self-provisioning team slots.


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


class TenantUser:
    def __init__(
        self,
        username: str,
        password_hash: str,
        display_name: str,
        role: str,
        tenant_id: str,
        allowed_datasets: list[str],
        email: str = "",
        role_title: str = "",
        provisioned: bool = False,
    ):
        self.username = username
        self.password_hash = password_hash
        self.display_name = display_name
        self.role = role  # "admin" or "user"
        self.tenant_id = tenant_id
        self.allowed_datasets = allowed_datasets  # dataset prefixes this user can see
        self.email = email
        self.role_title = role_title  # free-form role typed at signup ("Geologist", "Metallurgist", ...)
        self.provisioned = provisioned  # created via the team sign-up page

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "role_title": self.role_title,
            "provisioned": self.provisioned,
        }


USERS: dict[str, TenantUser] = {}

# ─── Provisioned user persistence ───
# Storage lives under a dedicated runtime directory on every deployment (VPS/local).
_RUNTIME_DIR = Path(__file__).resolve().parent.parent / "data"
PROVISION_FILE = _RUNTIME_DIR / "provisioned_users.json"
MAX_TEAM_SLOTS = 6
_TEAM_DATASETS = ["geology", "soil", "mining", "satellite", "regions"]


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
        "frank": TenantUser(
            username="frank",
            password_hash=_hash_password("voldemort578"),
            display_name="Frank (Admin)",
            role="admin",
            tenant_id="frank",
            allowed_datasets=["*"],  # admin sees everything
        ),
    }


# ─── Provisioned user store ───
def _load_provisioned():
    """Register team accounts persisted on disk (called once at import)."""
    if not PROVISION_FILE.exists():
        return
    try:
        payload = json.loads(PROVISION_FILE.read_text("utf-8"))
    except Exception as e:
        logger.error(f"Failed to read provisioned users: {e}")
        return
    for rec in payload.get("users", []):
        try:
            user = TenantUser(
                username=rec["username"],
                password_hash=rec["password_hash"],
                display_name=rec["display_name"],
                role=rec.get("role", "user"),
                tenant_id=rec.get("tenant_id", rec["username"]),
                allowed_datasets=rec.get("allowed_datasets", _TEAM_DATASETS),
                email=rec.get("email", ""),
                role_title=rec.get("role_title", ""),
                provisioned=True,
            )
            USERS[user.username] = user
        except Exception as e:
            logger.warning(f"Skipping invalid provisioned user record: {e}")


def _persist_users():
    """Atomically write the provisioned user set to disk."""
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for user in USERS.values():
        if not user.provisioned:
            continue
        records.append(
            {
                "username": user.username,
                "password_hash": user.password_hash,
                "display_name": user.display_name,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "allowed_datasets": user.allowed_datasets,
                "email": user.email,
                "role_title": user.role_title,
            }
        )
    payload = {"users": records}
    tmp = PROVISION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), "utf-8")
    os.replace(tmp, PROVISION_FILE)


def count_provisioned() -> int:
    return sum(1 for u in USERS.values() if u.provisioned)


def is_signup_open() -> bool:
    return count_provisioned() < MAX_TEAM_SLOTS


def signup_status() -> dict:
    filled = count_provisioned()
    return {
        "open": filled < MAX_TEAM_SLOTS,
        "total": MAX_TEAM_SLOTS,
        "filled": filled,
        "remaining": max(0, MAX_TEAM_SLOTS - filled),
    }


def _slugify(text: str) -> str:
    return re_sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


def re_sub(pattern: str, repl: str, text: str) -> str:
    import re

    return re.sub(pattern, repl, text)


def _unique_username(base: str) -> str:
    candidate = base or "team"
    i = 1
    while candidate in USERS:
        i += 1
        candidate = f"{base or 'team'}{i}"
    return candidate


def provision_user(name: str, email: str, password: str, role_title: str) -> TenantUser:
    """Create a team account. Raises ValueError with a human-readable reason."""
    if not is_signup_open():
        raise ValueError("Sign-up is now closed — all team slots are filled.")
    name = name.strip()
    email = email.strip().lower()
    role_title = (role_title or "Team Member").strip()
    if len(name) < 2:
        raise ValueError("Please enter your full name.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Please enter a valid email address.")
    for user in USERS.values():
        if user.email and user.email.lower() == email:
            raise ValueError("An account with that email already exists.")

    base = _slugify(email.split("@")[0]) or _slugify(name) or "team"
    username = _unique_username(base)
    user = TenantUser(
        username=username,
        password_hash=_hash_password(password),
        display_name=name,
        role="user",
        tenant_id=username,
        allowed_datasets=_TEAM_DATASETS,
        email=email,
        role_title=role_title,
        provisioned=True,
    )
    USERS[username] = user
    _persist_users()
    logger.info(f"Provisioned team account: {username} ({email}) — {count_provisioned()}/{MAX_TEAM_SLOTS} slots used")
    return user


# ─── Persona ───
def persona_prompt(user: Optional[TenantUser]) -> str:
    """Build the persona block injected into the system prompt for a team account."""
    if not user or not user.provisioned:
        return ""
    title = user.role_title or "mining professional"
    name = user.display_name or user.username
    return (
        f"You are the dedicated AI assistant for {name}, who works as a {title} at "
        f"Baguley Limited. Tailor every response to their professional perspective and "
        f"priorities as a {title} — use domain language, anticipate their reporting needs, "
        f"suggest next actions relevant to their role, and connect answers to their own "
        f"past conversations, memories, and the shared knowledge base."
    )


_init_users()
_load_provisioned()

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
        "email": user.email,
        "role_title": user.role_title,
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


def _resolve_user(identifier: str) -> Optional[TenantUser]:
    """Look up a user by username OR email (case-insensitive)."""
    identifier = identifier.strip()
    if not identifier:
        return None
    user = USERS.get(identifier)
    if user:
        return user
    low = identifier.lower()
    for u in USERS.values():
        if u.email and u.email.lower() == low:
            return u
    return None


def authenticate(username: str, password: str) -> Optional[str]:
    """Returns JWT token string if valid, None otherwise. Accepts username or email."""
    user = _resolve_user(username)
    if not user:
        # Constant-time comparison even for unknown users to prevent timing attacks
        bcrypt.checkpw(b"dummy", bcrypt.gensalt())
        logger.warning(f"Failed login attempt for unknown user: {username}")
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        logger.warning(f"Failed login attempt for user: {user.username}")
        return None
    logger.info(f"Successful login: {user.username} (role={user.role}, tenant={user.tenant_id})")
    return create_token(user.username)


def get_user(token_payload: dict) -> Optional[TenantUser]:
    username = token_payload.get("sub")
    return USERS.get(username)


def team_members() -> list[TenantUser]:
    """All non-admin accounts visible to Frank (baguley + provisioned team)."""
    return [u for u in USERS.values() if u.role != "admin"]


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