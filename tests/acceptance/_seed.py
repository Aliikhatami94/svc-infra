import os


def acceptance_seed():
    """
    No-op acceptance seed callable.

    This exists to verify that the CLI wiring in the acceptance harness works
    end-to-end (module import via PYTHONPATH, Typer invocation, and exit 0).
    Extend this to create tenants/users/API keys if your acceptance tests need them.
    """
    return None


def write_sentinel():
    """Tiny job target used by A10-02 to prove the jobs runner executes tasks.

    Writes a file at JOBS_SENTINEL (env) or /tmp/svc-infra-a10-jobs.ok.
    """
    path = os.environ.get("JOBS_SENTINEL", "/tmp/svc-infra-a10-jobs.ok")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("ok")
    return None
