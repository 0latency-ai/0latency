import { spawn } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface VerificationResult {
  success: boolean;
  durationMs: number;
  error?: string;
}

export async function verifyMemoryRoundTrip(apiKey: string): Promise<VerificationResult> {
  const startTime = Date.now();

  return new Promise((resolve) => {
    const serverPath = path.join(__dirname, "index.js");
    const child = spawn("node", [serverPath], {
      env: {
        ...process.env,
        ZERO_LATENCY_API_KEY: apiKey,
      },
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let timeoutId: NodeJS.Timeout;

    const cleanup = () => {
      clearTimeout(timeoutId);
      child.kill();
    };

    // Set 10s timeout
    timeoutId = setTimeout(() => {
      cleanup();
      resolve({
        success: false,
        durationMs: Date.now() - startTime,
        error: "Verification timed out after 10s",
      });
    }, 10000);

    child.stdout?.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr?.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("error", (err) => {
      cleanup();
      resolve({
        success: false,
        durationMs: Date.now() - startTime,
        error: `Failed to spawn server: ${err.message}`,
      });
    });

    // Wait for server to start (stderr message)
    const checkInterval = setInterval(() => {
      if (stderr.includes("0Latency MCP server running")) {
        clearInterval(checkInterval);
        runMemoryTest();
      }
    }, 100);

    async function runMemoryTest() {
      try {
        const testMessage = `Hello from init at ${new Date().toISOString()}`;

        // Send memory_add request
        const addRequest = {
          jsonrpc: "2.0",
          id: 1,
          method: "tools/call",
          params: {
            name: "memory_add",
            arguments: {
              agent_id: "init_test",
              human_message: testMessage,
              agent_message: "Init verification test",
            },
          },
        };

        child.stdin?.write(JSON.stringify(addRequest) + "\n");

        // Wait for response
        let responseReceived = false;
        const responseTimeout = setTimeout(() => {
          if (!responseReceived) {
            cleanup();
            resolve({
              success: false,
              durationMs: Date.now() - startTime,
              error: "No response from memory_add",
            });
          }
        }, 5000);

        child.stdout?.once("data", () => {
          responseReceived = true;
          clearTimeout(responseTimeout);

          // Memory added, now recall
          const recallRequest = {
            jsonrpc: "2.0",
            id: 2,
            method: "tools/call",
            params: {
              name: "memory_recall",
              arguments: {
                agent_id: "init_test",
                conversation_context: testMessage,
                budget_tokens: 1000,
              },
            },
          };

          child.stdin?.write(JSON.stringify(recallRequest) + "\n");

          // Wait for recall response
          child.stdout?.once("data", () => {
            cleanup();
            resolve({
              success: true,
              durationMs: Date.now() - startTime,
            });
          });
        });
      } catch (err: any) {
        cleanup();
        resolve({
          success: false,
          durationMs: Date.now() - startTime,
          error: `Test execution failed: ${err.message}`,
        });
      }
    }
  });
}
