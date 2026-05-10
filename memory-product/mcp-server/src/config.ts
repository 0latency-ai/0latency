import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

export interface ClientConfig {
  name: string;
  configPath: string;
  instructions?: string;
}

export function getClientConfig(clientType: string, customPath?: string): ClientConfig {
  if (customPath) {
    return {
      name: "Custom",
      configPath: customPath,
    };
  }

  const platform = process.platform;
  const home = os.homedir();

  switch (clientType) {
    case "claude-desktop":
      if (platform === "darwin") {
        return {
          name: "Claude Desktop (macOS)",
          configPath: path.join(home, "Library/Application Support/Claude/claude_desktop_config.json"),
        };
      } else if (platform === "linux") {
        return {
          name: "Claude Desktop (Linux)",
          configPath: path.join(home, ".config/Claude/claude_desktop_config.json"),
        };
      } else if (platform === "win32") {
        const appData = process.env.APPDATA || path.join(home, "AppData/Roaming");
        return {
          name: "Claude Desktop (Windows)",
          configPath: path.join(appData, "Claude/claude_desktop_config.json"),
        };
      }
      throw new Error(`Unsupported platform for Claude Desktop: ${platform}`);

    case "cursor":
      return {
        name: "Cursor",
        configPath: path.join(home, ".cursor/mcp.json"),
      };

    case "claude-code":
      return {
        name: "Claude Code",
        configPath: "",
        instructions: "Run: claude mcp add @0latency/mcp-server",
      };

    case "windsurf":
      return {
        name: "Windsurf",
        configPath: path.join(home, ".windsurf/mcp.json"),
      };

    default:
      throw new Error(`Unknown client type: ${clientType}`);
  }
}

export function getMcpConfigBlock(apiKey: string) {
  return {
    "0latency": {
      command: "npx",
      args: ["-y", "@0latency/mcp-server"],
      env: {
        ZERO_LATENCY_API_KEY: apiKey,
      },
    },
  };
}

export function mergeConfig(configPath: string, apiKey: string): void {
  let config: any = {};

  // Read existing config if it exists
  try {
    if (fs.existsSync(configPath)) {
      const content = fs.readFileSync(configPath, "utf-8");
      config = JSON.parse(content);
    }
  } catch (err: any) {
    if (err.code !== "ENOENT") {
      throw new Error(`Failed to read config file: ${err.message}`);
    }
  }

  // Ensure mcpServers exists
  if (!config.mcpServers) {
    config.mcpServers = {};
  }

  // Add or update 0latency entry
  config.mcpServers["0latency"] = {
    command: "npx",
    args: ["-y", "@0latency/mcp-server"],
    env: {
      ZERO_LATENCY_API_KEY: apiKey,
    },
  };

  // Ensure directory exists
  const dir = path.dirname(configPath);
  fs.mkdirSync(dir, { recursive: true });

  // Write back with 2-space indent
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n", "utf-8");
}

export function getApiKey(): string | null {
  // Check env var first
  if (process.env.ZERO_LATENCY_API_KEY) {
    return process.env.ZERO_LATENCY_API_KEY;
  }

  // Check credentials file
  const credsPath = path.join(os.homedir(), ".0latency/credentials");
  try {
    if (fs.existsSync(credsPath)) {
      const content = fs.readFileSync(credsPath, "utf-8").trim();
      if (content) {
        return content;
      }
    }
  } catch {
    // Ignore read errors
  }

  return null;
}
