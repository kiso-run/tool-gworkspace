import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture
def make_input():
    def _make(action="auth_status", **kwargs):
        args = {"action": action}
        args.update(kwargs)
        return {
            "args": args,
            "session": "test-session",
            "workspace": "/tmp/test-gworkspace-workspace",
            "session_secrets": {},
            "plan_outputs": [],
        }
    return _make


@pytest.fixture
def run_skill():
    """Run run.py as a subprocess with controlled stdin."""
    def _run(input_data, env=None):
        import os
        process_env = {"PATH": os.environ.get("PATH", "")}
        if env:
            process_env.update(env)
        return subprocess.run(
            [sys.executable, str(ROOT / "run.py")],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            env=process_env,
            timeout=10,
        )
    return _run


@pytest.fixture
def mock_gws():
    """Patch subprocess.run to mock gws calls. Returns (mock, set_response) pair.

    Usage:
        mock, respond = mock_gws
        respond(stdout="...", returncode=0)
        # or respond(stderr="...", returncode=1) for errors
    """
    responses = []

    def _set_response(stdout="", stderr="", returncode=0):
        responses.append(subprocess.CompletedProcess(
            args=["gws"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        ))

    with patch("run.subprocess.run") as mock_run:
        def side_effect(*args, **kwargs):
            if responses:
                return responses.pop(0)
            return subprocess.CompletedProcess(
                args=["gws"], returncode=0, stdout="", stderr="",
            )
        mock_run.side_effect = side_effect
        yield mock_run, _set_response
