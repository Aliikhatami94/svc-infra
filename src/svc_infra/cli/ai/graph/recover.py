def build_recovery_hint(cmd: str|None, err: str|None) -> str:
    """
    Produce a brief instruction block that the executor prepends to its next prompt.
    Keep this short and actionable.
    """
    cmd = (cmd or "").strip().lower()
    err = (err or "").lower()

    # Poetry cache common pitfall:
    # correct:  poetry cache clear <name> --all
    # wrong:    poetry cache clear --all <name>
    if "poetry" in cmd and "cache" in cmd and "not enough arguments" in err:
        return (
            "Correction: For Poetry, use `poetry cache clear <name> --all` "
            "(place <name> BEFORE `--all`). Valid names include `pypoetry` and `pypi`. "
            "Do not use `rm -rf` if a proper Poetry subcommand exists."
        )

    # Generic default
    return (
        "Before retrying, call a help command for the failing tool "
        "(e.g., `run_command: poetry cache --help`) and adjust the command accordingly. "
        "Do not repeat the same failing syntax."
    )