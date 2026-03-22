"""
Zero Latency Auth Module
GitHub OAuth + Google OAuth + Email/Password + JWT
"""
import os
import json
import secrets
import hashlib
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
import httpx
from passlib.hash import bcrypt
from fastapi import APIRouter, HTTPException, Request, Response, Query, Depends, Header, Cookie
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field, EmailStr

logger = logging.getLogger("zerolatency.auth")

# ─── Configuration ───────────────────────────────────────────────────────────

def _load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

# GitHub OAuth
_gh_creds = _load_json("/root/credentials/github_oauth.json")
GITHUB_CLIENT_ID = _gh_creds["client_id"]
GITHUB_CLIENT_SECRET = _gh_creds["client_secret"]

# Google OAuth
_google_creds = _load_json("/root/credentials/gmail_oauth_client.json")
_google_installed = _google_creds.get("installed", _google_creds.get("web", {}))
GOOGLE_CLIENT_ID = _google_installed["client_id"]
GOOGLE_CLIENT_SECRET = _google_installed["client_secret"]

# JWT
JWT_SECRET_PATH = "/root/credentials/jwt_secret.key"
with open(JWT_SECRET_PATH) as f:
    JWT_SECRET = f.read().strip()
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72  # 3 days

# Base URL
API_BASE = os.environ.get("API_BASE_URL", "https://api.0latency.ai")
SITE_BASE = os.environ.get("SITE_BASE_URL", "https://0latency.ai")

# ─── DB helpers (reuse existing connection pool) ─────────────────────────────

import sys
_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
from storage_multitenant import _db_execute_rows, _db_execute, _get_connection_pool


def _db_exec(query: str, params: tuple = None, fetch: bool = True):
    """Execute a query using the shared connection pool."""
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch and cur.description:
                return cur.fetchall()
            return []
    finally:
        pool.putconn(conn)


# ─── Ensure users table exists ───────────────────────────────────────────────

_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory_service.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE,
    name VARCHAR(256),
    avatar_url TEXT,
    github_id VARCHAR(64) UNIQUE,
    google_id VARCHAR(128) UNIQUE,
    password_hash TEXT,
    plan VARCHAR(16) NOT NULL DEFAULT 'free',
    tenant_id UUID REFERENCES memory_service.tenants(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON memory_service.users(email);
CREATE INDEX IF NOT EXISTS idx_users_github_id ON memory_service.users(github_id);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON memory_service.users(google_id);
"""

def ensure_users_table():
    """Create users table if it doesn't exist."""
    try:
        _db_exec(_USERS_TABLE_SQL, fetch=False)
        logger.info("Users table ensured")
    except Exception as e:
        logger.error(f"Failed to create users table: {e}")
        raise

# Run on import
try:
    ensure_users_table()
except Exception:
    logger.warning("Could not ensure users table on import — will retry on first request")


# ─── JWT helpers ─────────────────────────────────────────────────────────────

def create_jwt(user: dict) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": str(user["id"]),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "plan": user.get("plan", "free"),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, detail="Invalid token")


async def require_jwt(
    authorization: Optional[str] = Header(None),
    zl_token: Optional[str] = Cookie(None),
) -> dict:
    """Extract and validate JWT from Authorization header or cookie."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif zl_token:
        token = zl_token
    
    if not token:
        raise HTTPException(401, detail="Authentication required")
    
    return decode_jwt(token)


# ─── User CRUD ───────────────────────────────────────────────────────────────

def find_user_by_email(email: str) -> Optional[dict]:
    rows = _db_exec("""
        SELECT id, email, name, avatar_url, github_id, google_id, password_hash, plan, tenant_id
        FROM memory_service.users WHERE email = %s
    """, (email,))
    if rows:
        r = rows[0]
        return {
            "id": str(r[0]), "email": r[1], "name": r[2], "avatar_url": r[3],
            "github_id": r[4], "google_id": r[5], "password_hash": r[6],
            "plan": r[7], "tenant_id": str(r[8]) if r[8] else None,
        }
    return None


def find_user_by_github_id(github_id: str) -> Optional[dict]:
    rows = _db_exec("""
        SELECT id, email, name, avatar_url, github_id, google_id, password_hash, plan, tenant_id
        FROM memory_service.users WHERE github_id = %s
    """, (github_id,))
    if rows:
        r = rows[0]
        return {
            "id": str(r[0]), "email": r[1], "name": r[2], "avatar_url": r[3],
            "github_id": r[4], "google_id": r[5], "password_hash": r[6],
            "plan": r[7], "tenant_id": str(r[8]) if r[8] else None,
        }
    return None


def find_user_by_google_id(google_id: str) -> Optional[dict]:
    rows = _db_exec("""
        SELECT id, email, name, avatar_url, github_id, google_id, password_hash, plan, tenant_id
        FROM memory_service.users WHERE google_id = %s
    """, (google_id,))
    if rows:
        r = rows[0]
        return {
            "id": str(r[0]), "email": r[1], "name": r[2], "avatar_url": r[3],
            "github_id": r[4], "google_id": r[5], "password_hash": r[6],
            "plan": r[7], "tenant_id": str(r[8]) if r[8] else None,
        }
    return None


def create_user(email: str, name: str = None, avatar_url: str = None,
                github_id: str = None, google_id: str = None, 
                password_hash: str = None) -> dict:
    """Create a new user and auto-provision a tenant + API key."""
    user_id = str(uuid.uuid4())
    
    # Create tenant for this user
    from storage_multitenant import create_tenant
    tenant_info = create_tenant(name or email.split("@")[0], "free")
    tenant_id = tenant_info["tenant_id"]
    api_key = tenant_info["api_key"]
    
    _db_exec("""
        INSERT INTO memory_service.users (id, email, name, avatar_url, github_id, google_id, password_hash, tenant_id)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s::UUID)
    """, (user_id, email, name, avatar_url, github_id, google_id, password_hash, tenant_id), fetch=False)
    
    return {
        "id": user_id,
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
        "github_id": github_id,
        "google_id": google_id,
        "plan": "free",
        "tenant_id": tenant_id,
        "api_key": api_key,  # Only returned on first creation
        "is_new": True,
    }


def update_user(user_id: str, **kwargs):
    """Update user fields."""
    allowed = {"email", "name", "avatar_url", "github_id", "google_id", "password_hash", "plan"}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            updates.append(f"{k} = %s")
            params.append(v)
    if not updates:
        return
    updates.append("updated_at = now()")
    params.append(user_id)
    _db_exec(f"""
        UPDATE memory_service.users SET {', '.join(updates)} WHERE id = %s::UUID
    """, tuple(params), fetch=False)


# ─── OAuth state management (simple in-memory with TTL) ─────────────────────

_oauth_states: dict[str, tuple[str, float]] = {}  # state -> (provider, created_at)

def _create_oauth_state(provider: str) -> str:
    """Generate a random state parameter for OAuth CSRF protection."""
    import time
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = (provider, time.time())
    # Clean old states (>10 min)
    cutoff = time.time() - 600
    for k in list(_oauth_states.keys()):
        if _oauth_states[k][1] < cutoff:
            del _oauth_states[k]
    return state

def _verify_oauth_state(state: str, expected_provider: str) -> bool:
    import time
    if state not in _oauth_states:
        return False
    provider, created_at = _oauth_states.pop(state)
    return provider == expected_provider and (time.time() - created_at) < 600


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── GitHub OAuth ────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth consent screen."""
    state = _create_oauth_state("github")
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": f"{API_BASE}/auth/github/callback",
        "scope": "read:user user:email",
        "state": state,
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{qs}")


@router.get("/github/callback")
async def github_callback(code: str = Query(...), state: str = Query(...)):
    """Handle GitHub OAuth callback."""
    if not _verify_oauth_state(state, "github"):
        raise HTTPException(400, detail="Invalid or expired OAuth state")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{API_BASE}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
    
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(400, detail="GitHub OAuth failed: " + token_data.get("error_description", "unknown error"))
    
    # Get user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        gh_user = user_resp.json()
        
        # Get primary email
        emails_resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        emails = emails_resp.json()
    
    github_id = str(gh_user.get("id", ""))
    name = gh_user.get("name") or gh_user.get("login", "")
    avatar_url = gh_user.get("avatar_url", "")
    
    # Find primary email
    email = None
    if isinstance(emails, list):
        for e in emails:
            if e.get("primary") and e.get("verified"):
                email = e["email"]
                break
        if not email and emails:
            email = emails[0].get("email")
    if not email:
        email = gh_user.get("email")
    
    # Find or create user
    user = find_user_by_github_id(github_id)
    is_new = False
    api_key = None
    
    if user:
        # Update profile info
        update_user(user["id"], name=name, avatar_url=avatar_url, email=email)
        user["name"] = name
        user["email"] = email
    else:
        # Check if email already exists (link accounts)
        if email:
            user = find_user_by_email(email)
        if user:
            update_user(user["id"], github_id=github_id, avatar_url=avatar_url)
            user["github_id"] = github_id
        else:
            user = create_user(
                email=email or f"{github_id}@github.noemail",
                name=name,
                avatar_url=avatar_url,
                github_id=github_id,
            )
            is_new = True
            api_key = user.get("api_key")
    
    token = create_jwt(user)
    
    # Redirect to dashboard with token
    if is_new and api_key:
        redirect_url = f"{SITE_BASE}/login.html?token={token}&new=1&key={api_key}"
    else:
        redirect_url = f"{SITE_BASE}/login.html?token={token}"
    
    response = RedirectResponse(redirect_url)
    response.set_cookie(
        "zl_token", token,
        httponly=True, secure=True, samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        domain=".0latency.ai",
    )
    return response


# ─── Google OAuth ────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Redirect to Google OAuth consent screen."""
    state = _create_oauth_state("google")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{API_BASE}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{qs}")


@router.get("/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...)):
    """Handle Google OAuth callback."""
    if not _verify_oauth_state(state, "google"):
        raise HTTPException(400, detail="Invalid or expired OAuth state")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{API_BASE}/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()
    
    access_token = token_data.get("access_token")
    if not access_token:
        error = token_data.get("error_description", token_data.get("error", "unknown"))
        raise HTTPException(400, detail=f"Google OAuth failed: {error}")
    
    # Get user info
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        g_user = userinfo_resp.json()
    
    google_id = str(g_user.get("id", ""))
    email = g_user.get("email", "")
    name = g_user.get("name", "")
    avatar_url = g_user.get("picture", "")
    
    # Find or create user
    user = find_user_by_google_id(google_id)
    is_new = False
    api_key = None
    
    if user:
        update_user(user["id"], name=name, avatar_url=avatar_url, email=email)
        user["name"] = name
        user["email"] = email
    else:
        if email:
            user = find_user_by_email(email)
        if user:
            update_user(user["id"], google_id=google_id, avatar_url=avatar_url)
            user["google_id"] = google_id
        else:
            user = create_user(
                email=email,
                name=name,
                avatar_url=avatar_url,
                google_id=google_id,
            )
            is_new = True
            api_key = user.get("api_key")
    
    token = create_jwt(user)
    
    if is_new and api_key:
        redirect_url = f"{SITE_BASE}/login.html?token={token}&new=1&key={api_key}"
    else:
        redirect_url = f"{SITE_BASE}/login.html?token={token}"
    
    response = RedirectResponse(redirect_url)
    response.set_cookie(
        "zl_token", token,
        httponly=True, secure=True, samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        domain=".0latency.ai",
    )
    return response


# ─── Email/Password Auth ────────────────────────────────────────────────────

class EmailRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=256)

class EmailLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)

class AuthResponse(BaseModel):
    token: str
    user: dict
    is_new: bool = False
    api_key: Optional[str] = None


@router.post("/email/register", response_model=AuthResponse)
async def email_register(req: EmailRegisterRequest):
    """Register with email and password."""
    existing = find_user_by_email(req.email)
    if existing:
        raise HTTPException(409, detail="Email already registered. Try logging in.")
    
    password_hash = bcrypt.hash(req.password)
    user = create_user(
        email=req.email,
        name=req.name or req.email.split("@")[0],
        password_hash=password_hash,
    )
    
    token = create_jwt(user)
    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "plan": user["plan"],
            "tenant_id": user["tenant_id"],
        },
        is_new=True,
        api_key=user.get("api_key"),
    )


@router.post("/email/login", response_model=AuthResponse)
async def email_login(req: EmailLoginRequest):
    """Login with email and password."""
    user = find_user_by_email(req.email)
    if not user:
        raise HTTPException(401, detail="Invalid email or password")
    
    if not user.get("password_hash"):
        raise HTTPException(401, detail="This account uses OAuth login (GitHub/Google). Use that method instead.")
    
    if not bcrypt.verify(req.password, user["password_hash"]):
        raise HTTPException(401, detail="Invalid email or password")
    
    token = create_jwt(user)
    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "plan": user["plan"],
            "tenant_id": user["tenant_id"],
        },
    )


# ─── Current User ───────────────────────────────────────────────────────────

@router.get("/me")
async def get_current_user(claims: dict = Depends(require_jwt)):
    """Get current user profile from JWT."""
    user_id = claims.get("sub")
    rows = _db_exec("""
        SELECT u.id, u.email, u.name, u.avatar_url, u.github_id, u.google_id, 
               u.plan, u.tenant_id, u.created_at,
               t.api_key_hash, t.memory_limit, t.rate_limit_rpm, t.api_calls_count
        FROM memory_service.users u
        LEFT JOIN memory_service.tenants t ON u.tenant_id = t.id
        WHERE u.id = %s::UUID
    """, (user_id,))
    
    if not rows:
        raise HTTPException(404, detail="User not found")
    
    r = rows[0]
    return {
        "id": str(r[0]),
        "email": r[1],
        "name": r[2],
        "avatar_url": r[3],
        "github_id": r[4],
        "google_id": r[5],
        "plan": r[6],
        "tenant_id": str(r[7]) if r[7] else None,
        "created_at": str(r[8]),
        "tenant": {
            "memory_limit": r[10],
            "rate_limit_rpm": r[11],
            "api_calls_count": r[12] or 0,
        } if r[7] else None,
    }


# ─── API Key management (for authenticated users) ───────────────────────────

@router.post("/api-key/regenerate")
async def regenerate_api_key(claims: dict = Depends(require_jwt)):
    """Regenerate API key for the current user's tenant."""
    user_id = claims.get("sub")
    rows = _db_exec("""
        SELECT tenant_id FROM memory_service.users WHERE id = %s::UUID
    """, (user_id,))
    
    if not rows or not rows[0][0]:
        raise HTTPException(404, detail="No tenant associated with user")
    
    tenant_id = str(rows[0][0])
    
    # Generate new key
    new_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    new_hash = hashlib.sha256(new_key.encode()).hexdigest()
    
    _db_exec("""
        UPDATE memory_service.tenants SET api_key_hash = %s WHERE id = %s::UUID
    """, (new_hash, tenant_id), fetch=False)
    
    return {"api_key": new_key, "message": "New API key generated. Old key is immediately invalid."}
