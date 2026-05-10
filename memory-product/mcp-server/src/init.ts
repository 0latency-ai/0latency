import inquirer from "inquirer";
import { getClientConfig, mergeConfig, getApiKey } from "./config.js";
import { verifyMemoryRoundTrip } from "./verify.js";
import * as readline from "node:readline";

interface InitOptions {
  configPath?: string;
}

export async function runInit(options: InitOptions): Promise<void> {
  const startTime = Date.now();

  console.log("\n🚀 0Latency MCP Setup\n");

  // Step 1: Client selection
  const { client } = await inquirer.prompt([
    {
      type: "list",
      name: "client",
      message: "Which client are you configuring?",
      choices: [
        { name: "Claude Desktop", value: "claude-desktop" },
        { name: "Claude Code", value: "claude-code" },
        { name: "Cursor", value: "cursor" },
        { name: "Windsurf", value: "windsurf" },
        { name: "Other (print config)", value: "other" },
      ],
    },
  ]);

  if (client === "other") {
    printManualConfig();
    return;
  }

  const clientConfig = getClientConfig(client, options.configPath);

  // Step 2: Get API key
  let apiKey = getApiKey();

  if (!apiKey) {
    console.log("\nNo API key found. Get yours at: https://0latency.ai/quickstart\n");

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    apiKey = await new Promise<string>((resolve) => {
      rl.question("Paste your API key: ", (answer) => {
        rl.close();
        resolve(answer.trim());
      });
    });

    if (!apiKey || apiKey.length < 10) {
      console.error("❌ Invalid API key. Exiting.");
      process.exit(1);
    }
  } else {
    console.log("✓ Found API key");
  }

  // Step 3: Handle client-specific setup
  if (client === "claude-code") {
    console.log(`\n✓ API key ready: ${apiKey.slice(0, 8)}...`);
    console.log("\nFor Claude Code, run:");
    console.log("  claude mcp add @0latency/mcp-server");
    console.log(`  export ZERO_LATENCY_API_KEY=${apiKey}`);
    console.log("\nOr add to your project's .mcp.json manually.");
    return;
  }

  // Step 4: Write config
  try {
    mergeConfig(clientConfig.configPath, apiKey);
    console.log(`\n✓ Config written to: ${clientConfig.configPath}`);
  } catch (err: any) {
    console.error(`\n❌ Failed to write config: ${err.message}`);
    if (err.message.includes("EACCES")) {
      console.error("   Try running with appropriate permissions or check file permissions.");
    }
    process.exit(1);
  }

  // Step 5: Verify memory round-trip
  console.log("\n⏳ Verifying memory write+recall...");

  const verification = await verifyMemoryRoundTrip(apiKey);

  if (verification.success) {
    console.log(`✓ Memory verification: write+recall succeeded in ${(verification.durationMs / 1000).toFixed(1)}s`);
  } else {
    console.log(`⚠️  Memory verification failed: ${verification.error}`);
    console.log("   Your config was written, but the API test failed.");
    console.log("   Check your API key and network connection.");
  }

  // Step 6: Final instructions
  console.log(`\n✓ MCP configured for ${clientConfig.name}`);
  console.log(`✓ Restart ${clientConfig.name.split(" ")[0]} to apply changes\n`);

  const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`Total init time: ${totalTime}s\n`);
}

function printManualConfig(): void {
  console.log(`
Add this to your MCP config file:

{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your-api-key-here"
      }
    }
  }
}

Config file locations:
- Claude Desktop (macOS): ~/Library/Application Support/Claude/claude_desktop_config.json
- Claude Desktop (Linux): ~/.config/Claude/claude_desktop_config.json
- Claude Desktop (Windows): %APPDATA%/Claude/claude_desktop_config.json
- Cursor: ~/.cursor/mcp.json
- Windsurf: ~/.windsurf/mcp.json

Get your API key at: https://0latency.ai/quickstart
`);
}
