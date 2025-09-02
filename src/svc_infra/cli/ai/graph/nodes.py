import json, re, sys
from typing import Dict
from ai_infra.llm import CoreAgent
from ai_infra.llm.agents.custom.action_planner.main import run_action_planner

from .states import CLIAgentState
from ..constants import EXEC_POLICY
from ..context import cli_planner_sys_msg
from .utils import _print_plan_presentation
from .error_parser import extract_last_fail
from .recover import build_recovery_hint


async def plan_with_action_planner(state: CLIAgentState) -> CLIAgentState:
    # exec-only: load from file and skip planner (see Step 2 below if you adopt that path here)
    if state.get("exec_only") and state.get("plan_file"):
        import json
        from pathlib import Path
        p = Path(state["plan_file"])
        res = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"plan": [], "presentation_md": "", "approved": False}
    else:
        messages = [
            {"role": "system", "content": cli_planner_sys_msg()},
            {"role": "user", "content": state["query"]},
        ]
        res = await run_action_planner(
            messages=messages,
            tools=state["tools"],
            io_mode="terminal",
            provider=state["provider"],
            model_name=state["model_name"],
        )

    state["plan"] = res.get("plan", [])
    state["questions"] = res.get("questions", [])
    state["presentation_md"] = res.get("presentation_md", "")
    state["approved"] = bool(res.get("approved"))
    state["aborted"] = bool(res.get("aborted"))
    state["awaiting_approval"] = bool(res.get("awaiting_approval"))

    if (res.get("presentation_md") or "").strip():
        _print_plan_presentation(res["presentation_md"])

    # plan_only: end after planning (reuse router’s END branch)
    if state.get("plan_only"):
        # optionally save to file for parity
        pf = state.get("plan_file")
        if pf:
            import json, pathlib
            pathlib.Path(pf).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSaved plan to {pf}")
        state["aborted"] = True

    return state


async def execute_plan(state: CLIAgentState) -> CLIAgentState:
    agent = CoreAgent()

    async def _on_model_output_async(ai_msg):
        # If the user hit quit in the tool gate, nuke the assistant output.
        if state.get("hard_stop"):
            # Minimal, consistent abort payload for your transcript printer:
            from langchain_core.messages import AIMessage
            return AIMessage(content="RUN: <aborted>\nFAIL: aborted: hard stop")
        return ai_msg

    # Tool-call HITL (same UX and quiet-tools behavior)
    async def _hitl_gate(name: str, args: Dict):
        if state.get("hard_stop"):
            return {"action": "block", "replacement": "[aborted: hard stop]"}

        # budget check
        max_budget = state.get("max_tool_calls")
        if isinstance(max_budget, int) and max_budget >= 0:
            if state["tool_calls_used"] >= max_budget:
                state["hard_stop"] = True
                return {"action": "block", "replacement": "[aborted: budget exhausted]"}

        # pretty preview (unchanged)
        cmd = (
                args.get("command")
                or " && ".join(args.get("commands", []) or [])
                or args.get("cmd")
                or args.get("shell")
                or ""
        ).strip()
        if not state.get("quiet_tools"):
            if " --help" in cmd or cmd.endswith(" --help"):
                print(f"Probing help for: {cmd.split()[0:3]}")
            print(f"Executing -> {cmd or f'{name}({args})'}")

        from ..constants import DANGEROUS
        preview = cmd or f"{name}({json.dumps(args, separators=(',', ':'), ensure_ascii=False)})"
        if any(d in preview for d in DANGEROUS):
            return {"action": "block", "replacement": "[blocked: potentially destructive]"}

        if state.get("autoapprove_tools"):
            state["tool_calls_used"] += 1
            return {"action": "pass"}

        from asyncio import to_thread
        ans = (await to_thread(input, "Approve tool call? [y]es / [b]lock / [q]uit: ")).strip().lower()
        if ans in ("q", "quit", "exit", "stop"):
            state["hard_stop"] = True
            return {"action": "block", "replacement": "[aborted by user]"}
        if ans in ("b", "block"):
            return {"action": "block", "replacement": "[blocked by user]"}

        # approved
        state["tool_calls_used"] += 1
        return {"action": "pass"}

    # install the gate unless autoapprove
    if not state.get("autoapprove_tools"):
        agent.set_hitl(
            on_tool_call_async=_hitl_gate,
            on_model_output_async=_on_model_output_async,  # ← new
        )
    else:
        # Even in autoapprove mode, support emergency quit for consistency if you want:
        agent.set_hitl(on_model_output_async=_on_model_output_async)

    plan_steps = state.get("plan") or []
    questions  = state.get("questions") or []

    # --- NEW: split plan into tool vs. non-tool and print contextual steps
    tool_steps = [s for s in plan_steps if isinstance(s, dict) and s.get("kind") == "tool"]
    context_steps = [s for s in plan_steps if isinstance(s, dict) and s.get("kind") != "tool"]

    if context_steps:
        print("\nContext:")
        for s in context_steps:
            k = (s.get("kind") or "").lower()
            if k == "reason" and s.get("text"):
                print(" -", s["text"])
            elif k == "assert" and s.get("condition"):
                line = f"Assert: {s['condition']}"
                if s.get("on_fail_hint"):
                    line += f" (if false: {s['on_fail_hint']})"
                print(" -", line)
            elif k == "ask" and s.get("question"):
                print(" - Ask:", s["question"])

    # --- NEW: if no tool steps, synthesize a single best-effort command for trivial goals
    synthesized_steps = []
    if not tool_steps:
        q = (state.get("query") or "").lower().strip()
        if "path" in q and ("get" in q or "print" in q or "show" in q or "$path" in q):
            if sys.platform.startswith("win"):
                cmd = r'powershell -NoProfile -Command "$env:PATH"'
            else:
                cmd = r'''bash -lc 'printf "%s\n" "$PATH"' '''
            synthesized_steps = [{
                "kind": "tool",
                "tool": "run_command",
                "args": {"command": cmd.strip()},
                "rationale": "Print PATH (single-step, non-interactive)."
            }]

    effective_tool_steps = tool_steps or synthesized_steps

    if effective_tool_steps:
        exec_payload = json.dumps(effective_tool_steps, ensure_ascii=False, indent=2)
        exec_instruction = f"Execute this structured plan now (tool steps only):\n{exec_payload}"
    else:
        exec_instruction = f"Goal (no plan needed): {state['query']}\nExecute directly."

    if questions:
        exec_instruction += "\n\nOpen questions (answer if needed before execution):\n- " + "\n- ".join(questions)

    hint = (state.get("recovery_hint") or "").strip()
    if hint:
        print("\nApplying recovery hint:")
        print("  " + hint)

    exec_messages = [
        {"role": "system", "content": EXEC_POLICY},
        {"role": "system", "content": "You can manage the project as well as executing shell commands on a developer's local machine. Each command must run as-is. Output results using RUN/OK/FAIL markers. Be concise."},
        {"role": "system", "content": "If a DB connection is needed, prefer: `--database-url \"$DATABASE_URL\"`."},
        {"role": "human", "content": exec_instruction},
    ]

    print()
    resp = await agent.arun_agent(
        messages=exec_messages,
        provider=state["provider"],
        model_name=state["model_name"],
        tools=state["tools"],
        model_kwargs={"temperature": 0, "top_p": 1},
        tool_controls={"max_output_chars": 4000, "strip_ansi": True},
    )
    state["exec_response"] = resp

    # summarize error immediately (before router sends us to recover node)
    msgs = getattr(resp, "messages", None) or (resp.get("messages") if isinstance(resp, dict) else None)
    cmd, fail = extract_last_fail(msgs or [])
    state["had_error"] = bool(fail)
    if fail and re.search(r"\b(y/n|\[y/N\]|\(yes/no\))", fail, re.I):
        state["recovery_hint"] = (
            "The command appears to require interactive confirmation. "
            "Re-run with a non-interactive flag (e.g. --yes / --no-interaction) after checking '<cmd> --help'."
        )

    return state


async def recover_from_error(state: CLIAgentState) -> CLIAgentState:
    """
    Inspect the last exec_response, compute a short recovery hint,
    bump retry_count, and route back to execute_plan (bounded).
    """
    resp = state.get("exec_response")
    # surface 'messages' the same way your printer does
    msgs = getattr(resp, "messages", None)
    if msgs is None and isinstance(resp, dict):
        msgs = resp.get("messages")

    cmd, fail = extract_last_fail(msgs or [])
    state["last_cmd"] = cmd or ""
    state["last_error_text"] = fail or "command failed"
    state["recovery_hint"] = build_recovery_hint(cmd, fail)
    state["retry_count"] = int(state.get("retry_count") or 0) + 1
    # clear error flag so execute_plan can set it again if needed
    state["had_error"] = False
    return state