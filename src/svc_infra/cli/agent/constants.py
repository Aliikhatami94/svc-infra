PLAN_POLICY = (
    "ROLE=repo-orchestrator\n"
    "TASK=PLAN\n"
    "Assume working directory is the repo root: ${REPO_ROOT}.\n"
    "Output ONLY a short, numbered list of exact shell commands (one per line). "
    "No prose, no comments, no code fences.\n"
    "Prefer local tools inferred from project signals (svc-infra, poetry, npm/yarn/pnpm, mvn/gradle, make, docker compose). "
    "If a command isn’t on PATH and pyproject.toml exists, try `poetry run <cmd>` first.\n"
    "Avoid destructive operations (rm -rf, sudo) unless explicitly requested."
)

EXEC_POLICY = (
    "ROLE=repo-orchestrator\n"
    "TASK=EXEC\n"
    "Assume repo root unless 'cd'. For each command: print 'RUN: <command>' then 'OK' or 'FAIL: <reason>'. "
    "Keep returns concise; never paste long tool output back into the model.\n"
    "If a command may prompt for input, ADD a standard non-interactive flag where applicable "
    "(e.g., '--yes'/'-y', '--no-interaction', '--assume-yes', '--force', '--quiet'). "
    "Only add flags that exist for that CLI; check '<cmd> --help' first if unsure.\n"
    "On failure, do not repeat the same syntax. Probe '<cmd> --help', adjust once, retry once.\n"
)

DANGEROUS = (" rm -rf /", " mkfs", " shutdown", " reboot", ":(){:|:&};:", " dd if=", " > /dev/sda", " > /dev/nvme", " > /dev/vda")

# Directories we usually don't want to expand
_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "node_modules", ".venv", "venv", ".tox",
    "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".next", ".turbo", ".cache", ".gradle",
}

# Files we usually don't care to list (big or noisy)
_IGNORED_FILES = {
    ".DS_Store",
}

_PROJECT_SIGNALS = {
    # Build / package managers
    "python": ["pyproject.toml", "poetry.lock", "requirements.txt", "setup.py"],
    "node":   ["package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"],
    "java":   ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
    "docker": ["Dockerfile", "docker-compose.yml", "compose.yml"],
    "make":   ["Makefile"],
    "just":   ["Justfile"],
    "task":   ["Taskfile.yml", "Taskfile.yaml"],
    "pytest": ["pytest.ini", "pyproject.toml"],
}