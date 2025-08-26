from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

sys.path.insert(0, __import__('pathlib').Path(__file__).resolve().parents[1].joinpath('src').as_posix())

from svc_infra.db.ai import _print_exec_transcript, _redact  # noqa


def run_case_1():
    resp = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "RUN: echo hello\n"
                    "OK\n"
                    "RUN: echo hello\n"
                ),
            },
        ]
    }
    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_exec_transcript(resp, show_tool_output=False, max_lines=50, quiet_tools=True, show_error_context=True)
    out = buf.getvalue()
    assert "Step 1:" in out, out
    assert "OK" in out, out
    assert "Step 2:" not in out, out
    return out


def run_case_2():
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
        _print_exec_transcript(resp, show_tool_output=True, max_lines=50, quiet_tools=False, show_error_context=True)
    out = buf.getvalue()
    assert "Step 1:" in out, out
    assert "OK" in out, out
    assert "Step 2:" in out, out
    assert "Step 2 failed:" in out, out
    assert "TOOL(run_command): Postgres role 'postgres' does not exist" in out, out
    assert "PASSWORD 'secret'" not in out, out
    assert "'***'" in out, out
    assert "PGPASSWORD=super" not in out, out
    assert "PGPASSWORD=***" in out, out
    return out


def run_case_3():
    resp = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "RUN: brew services start postgresql\n"
                    "FAIL: Homebrew service command failed\n"
                ),
            },
            {
                "role": "tool",
                "name": "run_command",
                "content": (
                    "Error: Unknown command: services\n"
                    "Did you mean: 'search', 'install', 'service', etc.\n"
                ),
            },
        ]
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_exec_transcript(resp, show_tool_output=True, max_lines=50, quiet_tools=False, show_error_context=False)
    out = buf.getvalue()
    assert "TOOL(run_command): Homebrew service command failed" in out, out
    assert "🔍 Context:" not in out, out
    return out


if __name__ == "__main__":
    print("CASE 1 OUTPUT:\n" + run_case_1())
    print("CASE 2 OUTPUT:\n" + run_case_2())
    print("CASE 3 OUTPUT:\n" + run_case_3())
    print("All checks passed.")

