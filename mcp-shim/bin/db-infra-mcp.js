#!/usr/bin/env node
const { spawn } = require("child_process");

// Config from env with sane defaults
const UVX  = process.env.UVX_PATH || "uvx";
const REPO = process.env.SVC_INFRA_REPO || "https://github.com/Aliikhatami94/svc-infra.git";
const REF  = process.env.SVC_INFRA_REF  || "main";

/**
 * Use PEP 508 extras in the spec so uvx pulls the right deps into its
 * ephemeral venv. We’ll ask for Postgres v3 + async drivers.
 *
 * If you want to keep it lean, drop extras you don’t need.
 */
const SPEC = process.env.SVC_INFRA_SPEC
    || `git+${REPO}@${REF}#egg=svc-infra[pg,async]`;

// Run: uvx --from SPEC python -m svc_infra.db.setup.mcp --transport stdio <args>
const args = [
    "--quiet",
    ...(process.env.UVX_REFRESH ? ["--refresh"] : []),
    "--from", SPEC,
    // If you prefer --with pins instead of extras, keep these; harmless as a belt+suspenders:
    "--with", "psycopg[binary]",
    "--with", "asyncpg",
    "python", "-m", "svc_infra.db.setup.mcp",
    "--transport", "stdio",
    ...process.argv.slice(2),
];

/**
 * Propagate the parent env (harmless even if you don't rely on it),
 * and do not change cwd here — Python will chdir to project_root itself.
 */
const child = spawn(UVX, args, {
    stdio: "inherit",
    shell: process.platform === "win32",
    env: { ...process.env },
});

child.on("exit", code => process.exit(code));