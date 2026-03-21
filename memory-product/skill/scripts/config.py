"""
Centralized configuration for skill scripts.
NO hardcoded secrets. All values from environment variables.
"""
import os


def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        raise RuntimeError(f"Required environment variable {key} is not set")
    return val


def _optional_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_db_conn() -> str:
    return _require_env("MEMORY_DB_CONN")

def get_db_password() -> str:
    return _optional_env("MEMORY_DB_PASSWORD")

def get_google_api_key() -> str:
    return _require_env("GOOGLE_API_KEY")

def get_supabase_url() -> str:
    return _optional_env("MEMORY_SUPABASE_URL")

def get_supabase_key() -> str:
    return _optional_env("MEMORY_SUPABASE_KEY")
