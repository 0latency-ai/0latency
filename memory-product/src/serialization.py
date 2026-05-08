"""
Serialization utilities for structured JSON writes.

**Context:** P5.5 introduced a bug where datetime objects in audit event_data
caused TypeError during JSON serialization. The fix applied .isoformat() at the
construction site. This module consolidates that pattern into a canonical helper.

**Design decision:** Refused fallback to json.dumps(default=str) blanket approach.
That pattern silently str()s unknown types, masking real serialization bugs. This
helper raises TypeError for unknown types so they surface in tests.
"""

import json
from datetime import datetime
from uuid import UUID


def safe_json_dumps(obj, **kwargs) -> str:
    """
    Serialize object to JSON, handling datetime and UUID types.
    
    Raises TypeError for unknown types (no silent default=str fallback).
    
    Args:
        obj: Object to serialize
        **kwargs: Passed through to json.dumps (indent, etc.)
    
    Returns:
        JSON string
    
    Raises:
        TypeError: If obj contains types that cannot be serialized
    
    Examples:
        >>> safe_json_dumps({"created_at": datetime.now()})
        '{"created_at": "2026-05-08T12:34:56.789012"}'
        
        >>> safe_json_dumps({"id": UUID("550e8400-e29b-41d4-a716-446655440000")})
        '{"id": "550e8400-e29b-41d4-a716-446655440000"}'
    """
    def _default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, UUID):
            return str(o)
        elif isinstance(o, set):
            # Defensive: sets aren't JSON-serializable
            return list(o)
        else:
            # Raise TypeError to surface unknown types in tests
            raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    
    return json.dumps(obj, default=_default, **kwargs)
