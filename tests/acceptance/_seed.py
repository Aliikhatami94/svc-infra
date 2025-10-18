def acceptance_seed():
    """
    No-op acceptance seed callable.

    This exists to verify that the CLI wiring in the acceptance harness works
    end-to-end (module import via PYTHONPATH, Typer invocation, and exit 0).
    Extend this to create tenants/users/API keys if your acceptance tests need them.
    """
    return None
