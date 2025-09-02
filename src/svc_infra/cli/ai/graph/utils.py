import typer

def _print_plan_presentation(md: str) -> None:
    """Render the planner's markdown presentation as-is in blue."""
    if not (md or "").strip():
        return
    for line in md.splitlines():
        typer.secho(line, fg=typer.colors.BLUE, color=True)

def _on_enter(node_name: str, state: dict):
    if node_name == "plan_with_action_planner":
        print("\n→ Planning...")
    elif node_name == "execute_plan":
        rc = int(state.get("retry_count") or 0)
        if rc:
            print(f"\n→ Executing (retry {rc})...")
        else:
            print("\n→ Executing...")
        hint = (state.get("recovery_hint") or "").strip()
        if hint:
            print("Hint:", hint)
    elif node_name == "recover_from_error":
        print("\n→ Diagnosing failure and preparing fix...")

def _on_exit(node_name: str, state: dict):
    if node_name == "plan_with_action_planner":
        if state.get("presentation_md"):
            print("\n(plan ready)")
        if state.get("aborted"):
            print("(planning aborted)")
        elif state.get("awaiting_approval"):
            print("(awaiting approval)")
        elif not state.get("approved"):
            print("(plan not approved)")
    elif node_name == "execute_plan":
        if state.get("had_error"):
            print("(execution reported an error)")
        else:
            print("(execution finished)")