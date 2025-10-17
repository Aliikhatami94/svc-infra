import subprocess
import sys

import pytest

pytestmark = pytest.mark.jobs


def test_jobs_cli_run_one_loop():
    # Run one loop iteration to ensure command is wired and exits
    proc = subprocess.run(
        [sys.executable, "-m", "svc_infra.cli", "jobs", "run", "--max-loops", "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
