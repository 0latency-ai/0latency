"use strict";
/**
 * Error classes for the 0Latency SDK.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.RateLimitError = exports.AuthenticationError = exports.ZeroLatencyError = void 0;
/** Base exception for all 0Latency API errors. */
class ZeroLatencyError extends Error {
    statusCode;
    response;
    constructor(message, statusCode, response) {
        super(message);
        this.name = 'ZeroLatencyError';
        this.statusCode = statusCode;
        this.response = response;
    }
}
exports.ZeroLatencyError = ZeroLatencyError;
/** Raised when the API key is invalid or missing. */
class AuthenticationError extends ZeroLatencyError {
    constructor(message = 'Invalid or missing API key.', response) {
        super(message, 401, response);
        this.name = 'AuthenticationError';
    }
}
exports.AuthenticationError = AuthenticationError;
/** Raised when the API rate limit is exceeded. */
class RateLimitError extends ZeroLatencyError {
    retryAfter;
    constructor(message = 'Rate limit exceeded. Please retry later.', retryAfter = 60, response) {
        super(message, 429, response);
        this.name = 'RateLimitError';
        this.retryAfter = retryAfter;
    }
}
exports.RateLimitError = RateLimitError;
//# sourceMappingURL=errors.js.map