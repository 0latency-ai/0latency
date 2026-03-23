/**
 * Error classes for the 0Latency SDK.
 */

/** Base exception for all 0Latency API errors. */
export class ZeroLatencyError extends Error {
  statusCode?: number;
  response?: unknown;

  constructor(message: string, statusCode?: number, response?: unknown) {
    super(message);
    this.name = 'ZeroLatencyError';
    this.statusCode = statusCode;
    this.response = response;
  }
}

/** Raised when the API key is invalid or missing. */
export class AuthenticationError extends ZeroLatencyError {
  constructor(message = 'Invalid or missing API key.', response?: unknown) {
    super(message, 401, response);
    this.name = 'AuthenticationError';
  }
}

/** Raised when the API rate limit is exceeded. */
export class RateLimitError extends ZeroLatencyError {
  retryAfter: number;

  constructor(
    message = 'Rate limit exceeded. Please retry later.',
    retryAfter = 60,
    response?: unknown,
  ) {
    super(message, 429, response);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}
