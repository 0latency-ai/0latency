"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RateLimitError = exports.AuthenticationError = exports.ZeroLatencyError = void 0;
/**
 * Base exception for all 0Latency API errors.
 */
class ZeroLatencyError extends Error {
    constructor(message, statusCode, response) {
        super(message);
        this.name = 'ZeroLatencyError';
        this.statusCode = statusCode;
        this.response = response;
        Object.setPrototypeOf(this, ZeroLatencyError.prototype);
    }
}
exports.ZeroLatencyError = ZeroLatencyError;
/**
 * Raised when the API key is invalid or missing.
 */
class AuthenticationError extends ZeroLatencyError {
    constructor(message = 'Invalid or missing API key.', response) {
        super(message, 401, response);
        this.name = 'AuthenticationError';
        Object.setPrototypeOf(this, AuthenticationError.prototype);
    }
}
exports.AuthenticationError = AuthenticationError;
/**
 * Raised when the API rate limit is exceeded.
 */
class RateLimitError extends ZeroLatencyError {
    constructor(message = 'Rate limit exceeded. Please retry later.', response) {
        super(message, 429, response);
        this.name = 'RateLimitError';
        Object.setPrototypeOf(this, RateLimitError.prototype);
    }
}
exports.RateLimitError = RateLimitError;
//# sourceMappingURL=errors.js.map