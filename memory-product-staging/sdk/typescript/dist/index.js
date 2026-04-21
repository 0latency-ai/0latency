"use strict";
/**
 * 0Latency — Structured memory for AI agents.
 *
 * @example
 * ```typescript
 * import { Memory } from 'zerolatency';
 *
 * const memory = new Memory('your-api-key');
 * await memory.add('User prefers dark mode');
 * const results = await memory.recall('What does the user prefer?');
 * ```
 *
 * @packageDocumentation
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.RateLimitError = exports.AuthenticationError = exports.ZeroLatencyError = exports.Memory = void 0;
var client_js_1 = require("./client.js");
Object.defineProperty(exports, "Memory", { enumerable: true, get: function () { return client_js_1.Memory; } });
var errors_js_1 = require("./errors.js");
Object.defineProperty(exports, "ZeroLatencyError", { enumerable: true, get: function () { return errors_js_1.ZeroLatencyError; } });
Object.defineProperty(exports, "AuthenticationError", { enumerable: true, get: function () { return errors_js_1.AuthenticationError; } });
Object.defineProperty(exports, "RateLimitError", { enumerable: true, get: function () { return errors_js_1.RateLimitError; } });
//# sourceMappingURL=index.js.map