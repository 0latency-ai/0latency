/**
 * Base exception for all 0Latency API errors.
 */
export class ZeroLatencyError extends Error {
  public statusCode?: number;
  public response?: any;

  constructor(message: string, statusCode?: number, response?: any) {
    super(message);
    this.name = 'ZeroLatencyError';
    this.statusCode = statusCode;
    this.response = response;
    Object.setPrototypeOf(this, ZeroLatencyError.prototype);
  }
}

/**
 * Raised when the API key is invalid or missing.
 */
export class AuthenticationError extends ZeroLatencyError {
  constructor(message: string = 'Invalid or missing API key.', response?: any) {
    super(message, 401, response);
    this.name = 'AuthenticationError';
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

/**
 * Raised when the API rate limit is exceeded.
 */
export class RateLimitError extends ZeroLatencyError {
  constructor(message: string = 'Rate limit exceeded. Please retry later.', response?: any) {
    super(message, 429, response);
    this.name = 'RateLimitError';
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}
