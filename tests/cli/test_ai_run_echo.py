from __future__ import annotations

import io
from contextlib import redirect_stdout

from svc_infra.db.ai import _print_exec_transcript


def test_duplicate_run_lines_are_suppressed_within_same_message():
    resp = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "RUN: echo hello\n"
                    "OK\n"
                    "RUN: echo hello\n"  # duplicate echo of last command
                ),
            },
        ]
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_exec_transcript(resp, show_tool_output=False, max_lines=50, quiet_tools=True, show_error_context=True)
    out = buf.getvalue()

    assert "Step 1:" in out
    assert "OK" in out
    assert "Step 2:" not in out  # duplicate should be skipped


def test_duplicate_run_lines_are_suppressed_across_messages():
    resp = {
        "messages": [
            {
                "role": "assistant",
                "content": "RUN: echo hi\n",
            },
            {
                "role": "assistant",
                "content": "RUN: echo hi\n",  # repeated in subsequent message
            },
        ]
    }

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        _print_exec_transcript(resp, show_tool_output=False, max_lines=50, quiet_tools=True, show_error_context=True)
    out2 = buf2.getvalue()

    # Should only show Step 1 once
    assert out2.count("Step 1:") == 1
    assert "Step 2:" not in out2
