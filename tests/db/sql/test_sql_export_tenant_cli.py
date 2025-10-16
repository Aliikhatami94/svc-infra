from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


def test_sql_export_tenant_cli_json(tmp_path: Path):
    # Prepare sqlite DB file
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, tenant_id TEXT, name TEXT)")
    cur.execute("INSERT INTO items (tenant_id, name) VALUES (?, ?)", ("t1", "a"))
    cur.execute("INSERT INTO items (tenant_id, name) VALUES (?, ?)", ("t2", "b"))
    cur.execute("INSERT INTO items (tenant_id, name) VALUES (?, ?)", ("t1", "c"))
    conn.commit()
    conn.close()

    out_file = tmp_path / "out.json"
    env = os.environ.copy()
    env["SQL_URL"] = _sqlite_url(db_path)

    # Invoke CLI
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "svc_infra.cli",
            "sql",
            "export-tenant",
            "items",
            "--tenant-id",
            "t1",
            "--output",
            str(out_file),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out_file.read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert {r["name"] for r in data} == {"a", "c"}
