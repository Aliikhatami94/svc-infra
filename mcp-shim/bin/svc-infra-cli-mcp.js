#!/usr/bin/env node
const { spawn } = require("child_process");

const UVX  = process.env.UVX_PATH || "uvx";
const REPO = process.env.SVC_INFRA_REPO || "https://github.com/aliikhatami94/svc-infra.git";
const REF  = process.env.SVC_INFRA_REF  || "main";
const SPEC = `git+${REPO}@${REF}`;

const AI_INFRA_REPO = process.env.AI_INFRA_REPO || "https://github.com/aliikhatami94/ai-infra.git";
const AI_INFRA_REF  = process.env.AI_INFRA_REF  || "main";
const AI_INFRA_SPEC = `git+${AI_INFRA_REPO}@${AI_INFRA_REF}`;

const args = [
    "--quiet",
    ...(process.env.UVX_REFRESH ? ["--refresh"] : []),
    "--from", SPEC,          // primary package: svc-infra
    "--with", AI_INFRA_SPEC, // additional dep: ai-infra (pinned)
    "python", "-m", "svc_infra.mcp.svc_infra_mcp",
    "--transport", "stdio",
    ...process.argv.slice(2)
];

console.error("[svc-infra-cli-mcp] using", { SPEC, AI_INFRA_SPEC, UVX, refresh: !!process.env.UVX_REFRESH });
const child = spawn(UVX, args, { stdio: "inherit", shell: process.platform === "win32" });
child.on("exit", code => process.exit(code));