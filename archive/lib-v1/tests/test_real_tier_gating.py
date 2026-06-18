import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.real_site
def test_real_site_sample_requires_env():
    assert os.environ.get("ASK_CHATGPT_REAL") == "1"


def test_default_collection_deselects_real_site_tests():
    repo_root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items() if key != "ASK_CHATGPT_REAL"}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests/test_real_tier_gating.py::test_real_site_sample_requires_env" not in result.stdout
    assert "tests/test_driver.py::test_driver_happy_path_returns_latest_completed_turn" in result.stdout
