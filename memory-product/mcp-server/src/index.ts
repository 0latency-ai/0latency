#!/usr/bin/env node

import { Command } from "commander";
import { startMcpServer } from "./server.js";
import { runInit } from "./init.js";

const program = new Command();

program
  .name("0latency-mcp")
  .description("0Latency MCP Server - Persistent memory for AI agents")
  .version("0.2.2");

program
  .command("init")
  .description("Configure 0Latency MCP for your AI client")
  .option("--config-path <path>", "Custom config file path (for testing)")
  .action(async (options) => {
    try {
      await runInit(options);
    } catch (err: any) {
      console.error(`\nInit failed: ${err.message}`);
      process.exit(1);
    }
  });

// Default action: start MCP server
program.action(async () => {
  try {
    await startMcpServer();
  } catch (err: any) {
    console.error("Fatal:", err);
    process.exit(1);
  }
});

// If no command specified, run default (MCP server)
if (process.argv.length === 2) {
  startMcpServer().catch((err) => {
    console.error("Fatal:", err);
    process.exit(1);
  });
} else {
  program.parse(process.argv);
}
