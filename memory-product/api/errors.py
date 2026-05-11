"""
Centralized error envelope module for standardized API errors.

Replaces scattered HTTPException raises with consistent error responses
that include actionable hints and documentation links.

CP9 Phase 2 Track B2: Error Path UX
"""

from fastapi import HTTPException
from typing import Optional, Dict, Any


class APIError:
    """Standardized error envelope for all API errors."""
    
    def __init__(self, code: str, message: str, hint: str, docs_url: str):
        self.code = code
        self.message = message
        self.hint = hint
        self.docs_url = docs_url
    
    def to_dict(self, **extra) -> Dict[str, Any]:
        """Convert to dictionary for JSON response.
        
        Args:
            **extra: Additional fields to include in the error object
        """
        error_data = {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "docs_url": self.docs_url
        }
        error_data.update(extra)
        return {"error": error_data}


# ============================================================================
# PREDEFINED ERRORS FOR THE 4 COMMON ONBOARDING FAILURE MODES
# ============================================================================

INVALID_API_KEY = APIError(
    code="INVALID_API_KEY",
    message="API key is missing or invalid",
    hint="Provide your API key via either 'Authorization: Bearer zl_live_...' or 'X-API-Key: zl_live_...' header. Get your key at https://0latency.ai/dashboard",
    docs_url="https://0latency.ai/docs/troubleshooting#invalid-api-key"
)

MEMORY_LIMIT_REACHED = APIError(
    code="MEMORY_LIMIT_REACHED",
    message="You've reached your plan's memory limit",
    hint="Delete old memories or upgrade your plan at https://0latency.ai/dashboard/billing",
    docs_url="https://0latency.ai/docs/troubleshooting#memory-limit"
)

EXTRACTION_FAILED = APIError(
    code="EXTRACTION_FAILED",
    message="Memory extraction failed",
    hint="This is usually temporary. If it persists, contact support@0latency.ai with your request ID",
    docs_url="https://0latency.ai/docs/troubleshooting#extraction-failed"
)

RECALL_FAILED = APIError(
    code="RECALL_FAILED",
    message="Memory recall failed",
    hint="This is usually temporary. If it persists, contact support@0latency.ai with your request ID",
    docs_url="https://0latency.ai/docs/troubleshooting#recall-failed"
)


NOT_FOUND = APIError(
    code="NOT_FOUND",
    message="Resource not found",
    hint="The requested resource does not exist. Check your request parameters.",
    docs_url="https://0latency.ai/docs/troubleshooting#not-found"
)

VALIDATION_ERROR = APIError(
    code="VALIDATION_ERROR",
    message="Invalid request data",
    hint="Check your request format and required fields.",
    docs_url="https://0latency.ai/docs/troubleshooting#validation-error"
)

FORBIDDEN = APIError(
    code="FORBIDDEN",
    message="Access forbidden",
    hint="You do not have permission to access this resource.",
    docs_url="https://0latency.ai/docs/troubleshooting#forbidden"
)

SERVICE_UNAVAILABLE = APIError(
    code="SERVICE_UNAVAILABLE",
    message="Service temporarily unavailable",
    hint="This is usually temporary. Please try again in a few moments.",
    docs_url="https://0latency.ai/docs/troubleshooting#service-unavailable"
)

# Client-side error (for documentation - not raised by server)
NETWORK_CONNECTIVITY = APIError(
    code="NETWORK_CONNECTIVITY",
    message="Cannot connect to api.0latency.ai",
    hint="Check your internet connection, verify api.0latency.ai resolves (curl -I https://api.0latency.ai/health), and check firewall rules for outbound HTTPS",
    docs_url="https://0latency.ai/docs/troubleshooting#network-connectivity"
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def raise_api_error(
    error: APIError, 
    status_code: int = 400, 
    request_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    **extra
) -> None:
    """Raise HTTPException with standardized error envelope.
    
    Args:
        error: The predefined APIError to raise
        status_code: HTTP status code (default: 400)
        request_id: Optional request ID for tracking
        **extra: Additional fields to include in error response
        
    Raises:
        HTTPException with standardized error envelope
        
    Example:
        raise_api_error(INVALID_API_KEY, 401)
        raise_api_error(MEMORY_LIMIT_REACHED, 429, limit=10000, current=10000)
        raise_api_error(EXTRACTION_FAILED, 500, request_id="abc-123")
    """
    extra_fields = extra.copy()
    if request_id:
        extra_fields["request_id"] = request_id
    
    detail = error.to_dict(**extra_fields)
    if headers:
        raise HTTPException(status_code=status_code, detail=detail, headers=headers)
    else:
        raise HTTPException(status_code=status_code, detail=detail)


def raise_invalid_api_key(reason: str = "invalid") -> None:
    """Raise standardized invalid API key error (401).
    
    Args:
        reason: Specific reason (missing, invalid, revoked, suspended, not_found)
    """
    extra = {"reason": reason}
    raise_api_error(INVALID_API_KEY, 401, **extra)


def raise_memory_limit(limit: int, current: int = None, retry_after: int = None) -> None:
    """Raise standardized memory limit error (429).
    
    Args:
        limit: The memory limit for this tenant's plan
        current: Current memory count (optional)
    """
    extra = {"limit": limit}
    if current is not None:
        extra["current"] = current
    headers = None
    if retry_after is not None:
        extra["retry_after"] = retry_after
        headers = {"Retry-After": str(retry_after)}
    raise_api_error(MEMORY_LIMIT_REACHED, 429, headers=headers, **extra)


def raise_extraction_failed(request_id: Optional[str] = None, details: Optional[str] = None) -> None:
    """Raise standardized extraction failure error (500).
    
    Args:
        request_id: Request ID for tracking
        details: Optional additional error details
    """
    extra = {}
    if details:
        extra["details"] = details
    raise_api_error(EXTRACTION_FAILED, 500, request_id=request_id, **extra)


def raise_recall_failed(request_id: Optional[str] = None, details: Optional[str] = None) -> None:
    """Raise standardized recall failure error (500).
    
    Args:
        request_id: Request ID for tracking
        details: Optional additional error details
    """
    extra = {}
    if details:
        extra["details"] = details
    raise_api_error(RECALL_FAILED, 500, request_id=request_id, **extra)

def raise_not_found(resource: str = "Resource") -> None:
    """Raise standardized not found error (404).
    
    Args:
        resource: Name of the resource that was not found
    """
    extra = {"resource": resource}
    raise_api_error(NOT_FOUND, 404, **extra)


def raise_validation_error(details: str = None) -> None:
    """Raise standardized validation error (400).
    
    Args:
        details: Specific validation error details
    """
    extra = {}
    if details:
        extra["details"] = details
    raise_api_error(VALIDATION_ERROR, 400, **extra)


def raise_forbidden(reason: str = None) -> None:
    """Raise standardized forbidden error (403).
    
    Args:
        reason: Reason for denial
    """
    extra = {}
    if reason:
        extra["reason"] = reason
    raise_api_error(FORBIDDEN, 403, **extra)


def raise_service_unavailable(details: str = None) -> None:
    """Raise standardized service unavailable error (503).
    
    Args:
        details: Details about the unavailability
    """
    extra = {}
    if details:
        extra["details"] = details
    raise_api_error(SERVICE_UNAVAILABLE, 503, **extra)

