from __future__ import annotations
from typing import TypedDict, Any, List, Dict, Optional


class CLIAgentState(TypedDict, total=False):
    # ---- Inputs (from CLI flags) ----
    query: str
    provider: str
    model_name: str

    # Execution gating
    autoapprove_tools: bool          # --autoapprove or implied by --auto
    plan_only: bool                  # --plan-only
    exec_only: bool                  # --exec-only
    plan_file: str                   # --plan-file
    quiet_tools: bool                # --quiet-tools
    max_lines: int                   # --max-lines
    show_error_context: bool         # --show-error-context
    db_url: str                      # --db-url (for env + warnings)

    # ---- Shared tools ----
    tools: List[Dict[str, Any]]      # MCP tools available to planner & executor

    # ---- Planner outputs / status ----
    plan: List[Dict[str, Any]]       # [{rationale, tool, args}, ...]
    questions: List[str]
    presentation_md: str
    approved: bool
    aborted: bool
    awaiting_approval: bool

    # Optional planner metadata (useful for logs/UX)
    meta_complexity: str             # "trivial" | "simple" | "moderate" | "complex"
    meta_reason: str                 # brief reason for complexity
    skipped: bool                    # planner chose to skip (no plan needed)

    # ---- Execution outputs ----
    exec_response: Any               # CoreAgent result (messages / transcript / etc.)
    error: Optional[str]             # node-level error message if something fails

    # ---- Execution diagnostics / control ----
    had_error: bool                 # set by execute_plan when a FAIL is detected
    last_cmd: str                   # last RUN command that failed
    last_error_text: str            # terse error summary
    retry_count: int                # bounded retries
    recovery_hint: str              # extra instruction to guide the executor

    hard_stop: bool              # set to True to abort the run immediately
    max_tool_calls: int          # optional budget; when exhausted, we stop
    tool_calls_used: int         # running counter