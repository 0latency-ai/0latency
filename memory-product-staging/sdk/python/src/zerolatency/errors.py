"""Exception classes for the 0Latency SDK."""


class ZeroLatencyError(Exception):
    """Base exception for all 0Latency API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None) -> None:
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(ZeroLatencyError):
    """Raised when the API key is invalid or missing."""

    def __init__(self, message: str = "Invalid or missing API key.", response: dict | None = None) -> None:
        super().__init__(message, status_code=401, response=response)


class RateLimitError(ZeroLatencyError):
    """Raised when the API rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Please retry later.", response: dict | None = None) -> None:
        super().__init__(message, status_code=429, response=response)
