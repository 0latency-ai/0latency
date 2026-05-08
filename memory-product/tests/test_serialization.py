"""
CP8 P5.7 T5 - Tests for safe_json_dumps helper.
"""
import pytest
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4


def test_datetime_serialization():
    """Datetime objects serialize to ISO format."""
    from src.serialization import safe_json_dumps
    
    dt = datetime(2026, 5, 8, 12, 34, 56, 789012, tzinfo=timezone.utc)
    result = safe_json_dumps({"timestamp": dt})
    
    assert "2026-05-08T12:34:56.789012" in result
    # Verify round-trip
    parsed = json.loads(result)
    assert "timestamp" in parsed


def test_uuid_serialization():
    """UUID objects serialize to string format."""
    from src.serialization import safe_json_dumps
    
    uid = UUID("550e8400-e29b-41d4-a716-446655440000")
    result = safe_json_dumps({"id": uid})
    
    assert "550e8400-e29b-41d4-a716-446655440000" in result
    parsed = json.loads(result)
    assert parsed["id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_nested_mixed_types():
    """Handle nested dict with datetime, UUID, and primitives."""
    from src.serialization import safe_json_dumps
    
    data = {
        "event_id": uuid4(),
        "timestamp": datetime.now(timezone.utc),
        "metadata": {
            "count": 42,
            "tags": ["test", "audit"],
            "created_at": datetime(2026, 1, 1)
        }
    }
    
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    
    assert isinstance(parsed["metadata"]["count"], int)
    assert isinstance(parsed["metadata"]["tags"], list)


def test_unknown_type_raises_typeerror():
    """Unknown types raise TypeError, not silent str() conversion."""
    from src.serialization import safe_json_dumps
    
    class CustomClass:
        pass
    
    with pytest.raises(TypeError, match="CustomClass.*not JSON serializable"):
        safe_json_dumps({"obj": CustomClass()})


def test_set_converts_to_list():
    """Sets are converted to lists (defensive)."""
    from src.serialization import safe_json_dumps
    
    result = safe_json_dumps({"tags": {"a", "b", "c"}})
    parsed = json.loads(result)
    
    assert isinstance(parsed["tags"], list)
    assert set(parsed["tags"]) == {"a", "b", "c"}
