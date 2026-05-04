/**
 * Base exception for all 0Latency API errors.
 */
export declare class ZeroLatencyError extends Error {
    statusCode?: number;
    response?: any;
    constructor(message: string, statusCode?: number, response?: any);
}
/**
 * Raised when the API key is invalid or missing.
 */
export declare class AuthenticationError extends ZeroLatencyError {
    constructor(message?: string, response?: any);
}
/**
 * Raised when the API rate limit is exceeded.
 */
export declare class RateLimitError extends ZeroLatencyError {
    constructor(message?: string, response?: any);
}
//# sourceMappingURL=errors.d.ts.map