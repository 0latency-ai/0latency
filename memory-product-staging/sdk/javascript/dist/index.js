"use strict";
/**
 * 0Latency — Memory layer for AI agents.
 *
 * @packageDocumentation
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ZeroLatencyError = exports.RateLimitError = exports.AuthenticationError = exports.Memory = void 0;
var client_1 = require("./client");
Object.defineProperty(exports, "Memory", { enumerable: true, get: function () { return client_1.Memory; } });
var errors_1 = require("./errors");
Object.defineProperty(exports, "AuthenticationError", { enumerable: true, get: function () { return errors_1.AuthenticationError; } });
Object.defineProperty(exports, "RateLimitError", { enumerable: true, get: function () { return errors_1.RateLimitError; } });
Object.defineProperty(exports, "ZeroLatencyError", { enumerable: true, get: function () { return errors_1.ZeroLatencyError; } });
//# sourceMappingURL=index.js.map