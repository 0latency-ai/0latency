#!/usr/bin/env python3
"""
Session checkpoint metadata validation for CP7b Phase 1.
Validates metadata structure according to CP7b-SCOPE.md section 3.
"""
from fastapi import HTTPException
from typing import Optional, List, Any
import uuid


VALID_CHECKPOINT_TYPES = {"mid_thread", "end_of_thread", "auto_resume_meta", "tail_recovery"}
VALID_SOURCES = {"server_job", "agent", "extension"}


def validate_session_checkpoint_metadata(metadata: dict, memory_type: str) -> None:
    """
    Validate metadata for memory_type="session_checkpoint".
    Raises HTTPException with 400 status code if validation fails.
    
    Required schema (per CP7b-SCOPE.md section 3):
      - level: int (must be 1 for CP7b)
      - thread_id: uuid string
      - project_id: uuid string or null
      - thread_title: string or null
      - project_name: string or null
      - checkpoint_sequence: int (1, 2, 3...)
      - checkpoint_type: one of {mid_thread, end_of_thread, auto_resume_meta, tail_recovery}
      - turn_range: [start_turn, end_turn] array of 2 ints
      - turn_count: int
      - time_span_seconds: int
      - parent_memory_ids: array of uuid strings
      - child_memory_ids: array (reserved, can be empty)
      - parent_checkpoint_id: uuid string or null
      - source: one of {server_job, agent, extension}
    """
    if memory_type != "session_checkpoint":
        return  # Only validate session_checkpoint memory type
    
    if not metadata or not isinstance(metadata, dict):
        raise HTTPException(
            status_code=400,
            detail="session_checkpoint requires metadata object"
        )
    
    # Required fields
    required_fields = {
        "level": int,
        "thread_id": str,
        "checkpoint_sequence": int,
        "checkpoint_type": str,
        "turn_range": list,
        "turn_count": int,
        "time_span_seconds": int,
        "parent_memory_ids": list,
        "child_memory_ids": list,
        "source": str,
    }
    
    # Check required fields presence and type
    for field, expected_type in required_fields.items():
        if field not in metadata:
            raise HTTPException(
                status_code=400,
                detail=f"session_checkpoint metadata missing required field: {field}"
            )
        if not isinstance(metadata[field], expected_type):
            raise HTTPException(
                status_code=400,
                detail=f"session_checkpoint metadata field '{field}' must be {expected_type.__name__}, got {type(metadata[field]).__name__}"
            )
    
    # Validate level (must be 1 for CP7b)
    if metadata["level"] != 1:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint level must be 1 for CP7b (L2+ reserved for CP8), got {metadata['level']}"
        )
    
    # Validate thread_id format (UUID)
    try:
        uuid.UUID(metadata["thread_id"])
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint thread_id must be valid UUID, got '{metadata['thread_id']}'"
        )
    
    # Validate project_id if present (can be null)
    if "project_id" in metadata and metadata["project_id"] is not None:
        try:
            uuid.UUID(metadata["project_id"])
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail=f"session_checkpoint project_id must be valid UUID or null, got '{metadata['project_id']}'"
            )
    
    # Validate checkpoint_type
    if metadata["checkpoint_type"] not in VALID_CHECKPOINT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint checkpoint_type must be one of {VALID_CHECKPOINT_TYPES}, got '{metadata['checkpoint_type']}'"
        )
    
    # Validate checkpoint_sequence (must be positive)
    if metadata["checkpoint_sequence"] < 1:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint checkpoint_sequence must be >= 1, got {metadata['checkpoint_sequence']}"
        )
    
    # Validate turn_range (must be array of 2 ints)
    turn_range = metadata["turn_range"]
    if not isinstance(turn_range, list) or len(turn_range) != 2:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint turn_range must be [start_turn, end_turn], got {turn_range}"
        )
    if not all(isinstance(x, int) for x in turn_range):
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint turn_range must contain integers, got {turn_range}"
        )
    if turn_range[0] > turn_range[1]:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint turn_range start must be <= end, got {turn_range}"
        )
    
    # Validate turn_count (must be positive)
    if metadata["turn_count"] < 1:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint turn_count must be >= 1, got {metadata['turn_count']}"
        )
    
    # Validate time_span_seconds (must be non-negative)
    if metadata["time_span_seconds"] < 0:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint time_span_seconds must be >= 0, got {metadata['time_span_seconds']}"
        )
    
    # Validate parent_memory_ids (array of UUIDs)
    if not isinstance(metadata["parent_memory_ids"], list):
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint parent_memory_ids must be array, got {type(metadata['parent_memory_ids']).__name__}"
        )
    for i, mem_id in enumerate(metadata["parent_memory_ids"]):
        try:
            uuid.UUID(str(mem_id))
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail=f"session_checkpoint parent_memory_ids[{i}] must be valid UUID, got '{mem_id}'"
            )
    
    # Validate child_memory_ids (array, can be empty)
    if not isinstance(metadata["child_memory_ids"], list):
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint child_memory_ids must be array, got {type(metadata['child_memory_ids']).__name__}"
        )
    
    # Validate parent_checkpoint_id if present (can be null)
    if "parent_checkpoint_id" in metadata and metadata["parent_checkpoint_id"] is not None:
        try:
            uuid.UUID(metadata["parent_checkpoint_id"])
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail=f"session_checkpoint parent_checkpoint_id must be valid UUID or null, got '{metadata['parent_checkpoint_id']}'"
            )
    
    # Validate source
    if metadata["source"] not in VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"session_checkpoint source must be one of {VALID_SOURCES}, got '{metadata['source']}'"
        )
    
    # Optional fields validation (thread_title, project_name can be null or string)
    for field in ["thread_title", "project_name", "prompt_version"]:
        if field in metadata and metadata[field] is not None:
            if not isinstance(metadata[field], str):
                raise HTTPException(
                    status_code=400,
                    detail=f"session_checkpoint {field} must be string or null, got {type(metadata[field]).__name__}"
                )
