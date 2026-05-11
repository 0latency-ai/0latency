"""Canonical 401 messages for the auth layer.

Centralized so message text is consistent across:
- require_api_key in main.py
- any other auth surfaces (future MCP-side, OAuth bridge, etc.)

Message contracts are pinned by tests/test_auth_messages.py.
"""

MISSING_HEADER = (
    "Missing authentication header. "
    "Provide your API key via either 'Authorization: Bearer zl_live_...' or 'X-API-Key: zl_live_...' header. "
    "Get your key at https://0latency.ai/dashboard"
)

INVALID_FORMAT = (
    "API key format is invalid. "
    "Keys must start with 'zl_live_' and be 40 characters long."
)

NOT_FOUND = (
    "API key not found. If you recently rotated keys, update your integration. "
    "See https://docs.0latency.ai/auth/rotation."
)

REVOKED = (
    "API key revoked. Use your current active key. "
    "See https://0latency.ai/dashboard/keys to view active keys."
)

ACCOUNT_SUSPENDED = (
    "Account suspended. Contact support@0latency.ai."
)
