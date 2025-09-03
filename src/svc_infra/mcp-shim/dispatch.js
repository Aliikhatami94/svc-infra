#!/usr/bin/env node
const path = require("path");
const script = process.argv[2];
if (script === "auth-infra-mcp" || script === "db-management-mcp") {
    process.argv.splice(2, 1); // drop subcommand
    require(path.join(__dirname, "..", "src", "svc_infra", "mcp-shim", "bin", `${script}.js`));
} else {
    console.error("Usage: npx github:aliikhatami94/svc-infra <auth-infra-mcp|db-management-mcp> [args]");
    process.exit(1);
}