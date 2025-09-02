from __future__ import annotations

import io
from contextlib import redirect_stdout

from svc_infra.cli.agent.prints import _print_exec_transcript
from svc_infra.cli.agent.redaction import _redact


def test_redact_common_patterns():
    # URL credentials
    url = "postgresql://user:pass@host:5432/db?sslmode=disable"
    red = _redact(url)
    assert "user:pass@" not in red
    assert "postgresql://***:***@host:5432/db" in red

    # SQL quoted password
    sql = "CREATE ROLE myapp_user WITH LOGIN PASSWORD 'secret';"
    red = _redact(sql)
    assert "'secret'" not in red
    assert "'***'" in red

    # CLI password forms
    cli1 = "psql --password=secret --password secret2"
    red = _redact(cli1)
    assert "secret" not in red and "secret2" not in red
    assert "--password=***" in red and "--password ***" not in red  # normalized to = form

    # Env var
    env = "PGPASSWORD=topsecret psql -h localhost"
    red = _redact(env)
    assert "topsecret" not in red
    assert "PGPASSWORD=***" in red


def test_print_exec_transcript_streams_steps_and_redacts():
    resp = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "RUN: psql -U postgres -c \"CREATE ROLE myapp_user WITH LOGIN PASSWORD 'secret';\"\n"
                    "OK\n"
                    "RUN: export PGPASSWORD=super\n"
                    "FAIL: role 'postgres' does not exist\n"
                    "NEXT: Suggestions\n"
                    "- Ensure you can connect as a superuser\n"
                ),
            },
            {
                "role": "tool",
                "name": "run_command",
                "content": "Error: role 'postgres' does not exist",
            },
        ]
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_exec_transcript(resp, show_tool_output=True, max_lines=50, quiet_tools=False)
    out = buf.getvalue()

    # Step numbering and statuses
    assert "Step 1:" in out
    assert "OK" in out
    assert "Step 2:" in out
    assert "Step 2 failed:" in out

    # Redactions
    assert "PASSWORD 'secret'" not in out
    assert "'***'" in out
    assert "PGPASSWORD=super" not in out
    assert "PGPASSWORD=***" in out

    # Tool error summary
    assert "TOOL(run_command): Postgres role 'postgres' does not exist" in out

