"""
Zero Latency Auth Module
Supabase Auth integration — JWT verification via getUser(), profile management, API key management.
"""
import os
import sys
import secrets
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, Depends
from supabase import create_client, Client

logger = logging.getLogger("zerolatency.auth")

# ─── Supabase Client ────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("MEMORY_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("MEMORY_SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.warning("MEMORY_SUPABASE_URL or MEMORY_SUPABASE_KEY not set — auth will fail")

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_KEY else None

# ─── DB helpers (reuse existing connection pool) ─────────────────────────────

_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
from storage_multitenant import _get_connection_pool, create_tenant


def _db_exec(query: str, params: tuple = None, fetch: bool = True):
    """Execute a query using the shared connection pool."""
    pool = _get_connection_pool()
    conn = pool.getconn()
    try:
        if conn.status == 0:
            conn.autocommit = True
        elif not conn.autocommit:
            try:
                conn.commit()
            except Exception:
                conn.rollback()
            conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch and cur.description:
                return cur.fetchall()
            return []
    finally:
        pool.putconn(conn)


# ─── Auth dependency ─────────────────────────────────────────────────────────

async def require_jwt(
    authorization: Optional[str] = Header(None),
    zl_token: Optional[str] = Cookie(None),
) -> dict:
    """Validate Supabase JWT via getUser() and return claims dict."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif zl_token:
        token = zl_token

    if not token:
        raise HTTPException(401, detail="Authentication required")

    if not _supabase:
        raise HTTPException(500, detail="Auth service not configured")

    try:
        res = _supabase.auth.get_user(token)
    except Exception as e:
        logger.warning(f"Supabase auth error: {e}")
        raise HTTPException(401, detail="Invalid or expired token")

    if not res or not res.user:
        raise HTTPException(401, detail="Invalid or expired token")

    return {
        "sub": str(res.user.id),
        "email": res.user.email or "",
    }


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])

# Base URL
SITE_BASE = os.environ.get("SITE_BASE_URL", "https://0latency.ai")


# ─── Current User ───────────────────────────────────────────────────────────

@router.get("/me")
async def get_current_user(claims: dict = Depends(require_jwt)):
    """Get current user profile. Auto-provisions tenant for new users."""
    user_id = claims["sub"]

    rows = _db_exec("""
        SELECT p.id, p.name, p.avatar_url, p.plan, p.tenant_id,
               p.stripe_customer_id, p.created_at,
               t.api_key_hash, t.memory_limit, t.rate_limit_rpm, t.api_calls_count, t.api_key_live
        FROM memory_service.profiles p
        LEFT JOIN memory_service.tenants t ON p.tenant_id = t.id
        WHERE p.id = %s::UUID
    """, (user_id,))

    if not rows:
        raise HTTPException(404, detail="Profile not found")

    r = rows[0]
    tenant_id = r[4]
    api_key = r[11]
    is_new = False

    # Auto-provision tenant for new users (first login after Supabase signup)
    if not tenant_id:
        name = r[1] or claims.get("email", "").split("@")[0] or "user"
        tenant_info = create_tenant(name, "free")
        tenant_id = tenant_info["tenant_id"]
        api_key = tenant_info["api_key"]
        is_new = True

        _db_exec("""
            UPDATE memory_service.profiles SET tenant_id = %s::UUID, updated_at = now()
            WHERE id = %s::UUID
        """, (tenant_id, user_id), fetch=False)

        # Re-fetch tenant info
        t_rows = _db_exec("""
            SELECT api_key_hash, memory_limit, rate_limit_rpm, api_calls_count, api_key_live
            FROM memory_service.tenants WHERE id = %s::UUID
        """, (tenant_id,))
        if t_rows:
            tr = t_rows[0]
            return {
                "id": str(r[0]),
                "email": claims.get("email", ""),
                "name": r[1],
                "avatar_url": r[2],
                "plan": r[3] or "free",
                "tenant_id": str(tenant_id),
                "created_at": str(r[6]),
                "api_key": api_key,
                "is_new": True,
                "tenant": {
                    "memory_limit": tr[1],
                    "rate_limit_rpm": tr[2],
                    "api_calls_count": tr[3] or 0,
                },
            }

    return {
        "id": str(r[0]),
        "email": claims.get("email", ""),
        "name": r[1],
        "avatar_url": r[2],
        "plan": r[3] or "free",
        "tenant_id": str(tenant_id) if tenant_id else None,
        "created_at": str(r[6]),
        "api_key": api_key,
        "is_new": is_new,
        "tenant": {
            "memory_limit": r[8],
            "rate_limit_rpm": r[9],
            "api_calls_count": r[10] or 0,
        } if tenant_id else None,
    }


# ─── API Key management ─────────────────────────────────────────────────────

@router.get("/api-key")
async def get_api_key(claims: dict = Depends(require_jwt)):
    """Get the current user's tenant API key."""
    user_id = claims["sub"]
    rows = _db_exec("""
        SELECT t.api_key_live
        FROM memory_service.profiles p
        JOIN memory_service.tenants t ON p.tenant_id = t.id
        WHERE p.id = %s::UUID
    """, (user_id,))

    if not rows or not rows[0][0]:
        raise HTTPException(404, detail="No API key found")

    return {"api_key": rows[0][0]}


@router.post("/api-key/regenerate")
async def regenerate_api_key(claims: dict = Depends(require_jwt)):
    """Regenerate API key for the current user's tenant."""
    user_id = claims["sub"]
    rows = _db_exec("""
        SELECT tenant_id FROM memory_service.profiles WHERE id = %s::UUID
    """, (user_id,))

    if not rows or not rows[0][0]:
        raise HTTPException(404, detail="No tenant associated with user")

    tenant_id = str(rows[0][0])

    new_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    new_hash = hashlib.sha256(new_key.encode()).hexdigest()

    _db_exec("""
        UPDATE memory_service.tenants SET api_key_hash = %s, api_key_live = %s WHERE id = %s::UUID
    """, (new_hash, new_key, tenant_id), fetch=False)

    return {"api_key": new_key, "message": "New API key generated. Old key is immediately invalid."}
