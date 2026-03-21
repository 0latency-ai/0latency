"""
Structured JSON Schemas — Developer-defined extraction templates.
Feature gap #6 vs mem0: Custom memory schemas for structured output.
"""

import json
from typing import Optional
from storage_multitenant import _db_execute_rows


def create_schema(tenant_id: str, name: str, schema_definition: dict,
                  extraction_prompt: str = None) -> dict:
    """
    Create a custom extraction schema.
    
    schema_definition follows JSON Schema format, e.g.:
    {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "action_items": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["sentiment"]
    }
    """
    rows = _db_execute_rows("""
        INSERT INTO memory_service.extraction_schemas 
            (tenant_id, name, schema_definition, extraction_prompt)
        VALUES (%s::UUID, %s, %s::jsonb, %s)
        ON CONFLICT (tenant_id, name) DO UPDATE
        SET schema_definition = EXCLUDED.schema_definition,
            extraction_prompt = COALESCE(EXCLUDED.extraction_prompt, 
                                         memory_service.extraction_schemas.extraction_prompt)
        RETURNING id, created_at
    """, (tenant_id, name, json.dumps(schema_definition), extraction_prompt), tenant_id=tenant_id)
    
    if rows:
        return {
            "id": str(rows[0][0]),
            "name": name,
            "schema": schema_definition,
            "created_at": str(rows[0][1]),
        }
    raise RuntimeError("Failed to create schema")


def get_schema(tenant_id: str, name: str) -> Optional[dict]:
    """Get a schema by name."""
    rows = _db_execute_rows("""
        SELECT id, name, schema_definition, extraction_prompt, active
        FROM memory_service.extraction_schemas
        WHERE tenant_id = %s::UUID AND name = %s AND active = true
    """, (tenant_id, name), tenant_id=tenant_id)
    
    if rows:
        r = rows[0]
        return {
            "id": str(r[0]),
            "name": str(r[1]),
            "schema": r[2] if isinstance(r[2], dict) else json.loads(str(r[2])),
            "extraction_prompt": str(r[3]) if r[3] else None,
            "active": bool(r[4]),
        }
    return None


def list_schemas(tenant_id: str) -> list[dict]:
    """List all active schemas for a tenant."""
    rows = _db_execute_rows("""
        SELECT id, name, schema_definition, active, created_at
        FROM memory_service.extraction_schemas
        WHERE tenant_id = %s::UUID AND active = true
        ORDER BY created_at DESC
    """, (tenant_id,), tenant_id=tenant_id)
    
    return [{
        "id": str(r[0]),
        "name": str(r[1]),
        "schema": r[2] if isinstance(r[2], dict) else json.loads(str(r[2])),
        "active": bool(r[3]),
        "created_at": str(r[4]),
    } for r in (rows or [])]


def delete_schema(tenant_id: str, schema_id: str) -> bool:
    """Soft-delete a schema."""
    rows = _db_execute_rows("""
        UPDATE memory_service.extraction_schemas 
        SET active = false
        WHERE id = %s::UUID AND tenant_id = %s::UUID
        RETURNING id
    """, (schema_id, tenant_id), tenant_id=tenant_id)
    return bool(rows)


def validate_custom_fields(custom_fields: dict, schema: dict) -> tuple[bool, str]:
    """
    Validate custom_fields against a JSON schema definition.
    Lightweight validation without jsonschema library.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # Check required fields
    for field in required:
        if field not in custom_fields:
            return False, f"Missing required field: {field}"
    
    # Type check
    for field_name, field_value in custom_fields.items():
        if field_name not in properties:
            continue  # Allow extra fields
        
        expected = properties[field_name]
        expected_type = expected.get("type")
        
        if expected_type == "string" and not isinstance(field_value, str):
            return False, f"Field '{field_name}' must be a string"
        elif expected_type == "number" and not isinstance(field_value, (int, float)):
            return False, f"Field '{field_name}' must be a number"
        elif expected_type == "boolean" and not isinstance(field_value, bool):
            return False, f"Field '{field_name}' must be a boolean"
        elif expected_type == "array" and not isinstance(field_value, list):
            return False, f"Field '{field_name}' must be an array"
        
        # Enum check
        if "enum" in expected and field_value not in expected["enum"]:
            return False, f"Field '{field_name}' must be one of {expected['enum']}"
        
        # Range check
        if expected_type == "number":
            if "minimum" in expected and field_value < expected["minimum"]:
                return False, f"Field '{field_name}' must be >= {expected['minimum']}"
            if "maximum" in expected and field_value > expected["maximum"]:
                return False, f"Field '{field_name}' must be <= {expected['maximum']}"
    
    return True, "valid"


def build_schema_extraction_prompt(schema: dict) -> str:
    """
    Build an extraction prompt fragment from a schema definition.
    This gets appended to the main extraction prompt to guide custom field extraction.
    """
    properties = schema.get("schema", {}).get("properties", {})
    if not properties:
        return ""
    
    lines = ["\n\nADDITIONAL CUSTOM FIELDS TO EXTRACT:"]
    lines.append("For each memory, also extract these custom fields into a 'custom_fields' object:\n")
    
    for field_name, field_def in properties.items():
        field_type = field_def.get("type", "string")
        desc = field_def.get("description", "")
        
        line = f"- **{field_name}** ({field_type})"
        if desc:
            line += f": {desc}"
        if "enum" in field_def:
            line += f" [options: {', '.join(field_def['enum'])}]"
        if "minimum" in field_def or "maximum" in field_def:
            line += f" [range: {field_def.get('minimum', '...')}-{field_def.get('maximum', '...')}]"
        
        lines.append(line)
    
    custom_prompt = schema.get("extraction_prompt")
    if custom_prompt:
        lines.append(f"\nCustom instructions: {custom_prompt}")
    
    return "\n".join(lines)
