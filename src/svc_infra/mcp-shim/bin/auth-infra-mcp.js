#!/usr/bin/env node
const { spawn } = require("child_process");

const UVX  = process.env.UVX_PATH || "uvx";
const REPO = process.env.SVC_INFRA_REPO || "https://github.com/aliikhatami94/svc-infra.git";
const REF  = process.env.SVC_INFRA_REF  || "main";
const SPEC = `git+${REPO}@${REF}`;

const args = [
    "--quiet",
    ...(process.env.UVX_REFRESH ? ["--refresh"] : []),
    "--from", SPEC,
    "python", "-m", "svc_infra.auth.mcp",
    "--transport", "stdio",
    ...process.argv.slice(2)
];

const child = spawn(UVX, args, { stdio: "inherit", shell: process.platform === "win32" });
child.on("exit", code => process.exit(code));