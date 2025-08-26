from __future__ import annotations

import io
from contextlib import redirect_stdout

from svc_infra.db.ai import _print_exec_transcript


def test_brew_error_summary_and_context_printing():
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
        _print_exec_transcript(resp, show_tool_output=True, max_lines=50, quiet_tools=False, show_error_context=True)
    out = buf.getvalue()

    # Summary and context should appear
    assert "TOOL(run_command): Homebrew service command failed" in out
    assert "🔍 Context:" in out
    assert "Unknown command: services" in out


def test_error_context_toggle_off():
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

    # Summary should appear but no context block
    assert "TOOL(run_command): Homebrew service command failed" in out
    assert "🔍 Context:" not in out

