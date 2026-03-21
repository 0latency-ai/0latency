"""
Centralized configuration — Single source of truth for all env vars.
NO hardcoded secrets. Ever. If an env var isn't set, we fail loudly.
"""
import os


def _require_env(key: str, allow_empty: bool = False) -> str:
    """Get required env var or raise."""
    val = os.environ.get(key, "")
    if not val and not allow_empty:
        raise RuntimeError(f"Required environment variable {key} is not set")
    return val


def _optional_env(key: str, default: str = "") -> str:
    """Get optional env var with safe default (never a secret)."""
    return os.environ.get(key, default)


# --- Database ---
def get_db_conn() -> str:
    return _require_env("MEMORY_DB_CONN")

def get_db_password() -> str:
    return _optional_env("MEMORY_DB_PASSWORD")

# --- Embedding / LLM ---
def get_google_api_key() -> str:
    return _require_env("GOOGLE_API_KEY")

def get_openai_api_key() -> str:
    return _optional_env("OPENAI_API_KEY")

# --- Supabase ---
def get_supabase_url() -> str:
    return _optional_env("MEMORY_SUPABASE_URL")

def get_supabase_key() -> str:
    return _optional_env("MEMORY_SUPABASE_KEY")

# --- Admin ---
def get_admin_key() -> str:
    return _require_env("MEMORY_ADMIN_KEY")

# --- CORS ---
def get_cors_origins() -> list[str]:
    raw = _optional_env("CORS_ORIGINS", "https://164.90.156.169")
    return [o.strip() for o in raw.split(",") if o.strip()]
