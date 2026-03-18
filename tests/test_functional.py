"""Functional tests — exercise run.py via subprocess (stdin JSON → stdout/stderr + exit code).

Mock the ``gws`` binary with shell shims prepended to $PATH.
"""
from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gws_shim(tmp_path: Path, script: str) -> dict:
    """Create a mock ``gws`` shell script and return env with PATH pointing to it."""
    shim = tmp_path / "gws"
    shim.write_text(textwrap.dedent(script))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    env = {"PATH": f"{tmp_path}:{os.environ.get('PATH', '')}"}
    return env


def _run_tool(input_data, env=None, *, raw_stdin: str | None = None):
    """Run run.py as a subprocess. Accepts dict *or* raw string for stdin."""
    process_env = {"PATH": os.environ.get("PATH", "")}
    if env:
        process_env.update(env)
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(input_data)
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py")],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=process_env,
        timeout=10,
    )


def _make_input(action: str | None = None, **kwargs) -> dict:
    args: dict = {}
    if action is not None:
        args["action"] = action
    args.update(kwargs)
    return {
        "args": args,
        "session": "test-session",
        "workspace": "/tmp/test-gworkspace-workspace",
        "session_secrets": {},
        "plan_outputs": [],
    }


# ---------------------------------------------------------------------------
# M9 — Happy paths
# ---------------------------------------------------------------------------

class TestHappyPaths:
    def test_raw_action(self, tmp_path):
        env = _make_gws_shim(tmp_path, """\
            #!/bin/sh
            echo "Authenticated"
        """)
        result = _run_tool(_make_input("raw", command="auth status"), env)
        assert result.returncode == 0
        assert "Authenticated" in result.stdout

    def test_drive_list(self, tmp_path):
        drive_json = json.dumps({
            "files": [
                {
                    "id": "f1",
                    "name": "doc.txt",
                    "mimeType": "text/plain",
                    "modifiedTime": "2025-01-01T00:00:00Z",
                }
            ]
        })
        env = _make_gws_shim(tmp_path, f"""\
            #!/bin/sh
            echo '{drive_json}'
        """)
        result = _run_tool(_make_input("drive_list"), env)
        assert result.returncode == 0
        assert "doc.txt" in result.stdout
        assert "f1" in result.stdout


# ---------------------------------------------------------------------------
# M9 — Error paths
# ---------------------------------------------------------------------------

class TestErrors:
    def test_missing_action(self, tmp_path):
        env = _make_gws_shim(tmp_path, "#!/bin/sh\necho ok")
        # args has no "action" key
        result = _run_tool(_make_input(), env)
        assert result.returncode == 1
        assert "'action' argument is required" in result.stderr

    def test_unknown_action(self, tmp_path):
        env = _make_gws_shim(tmp_path, "#!/bin/sh\necho ok")
        result = _run_tool(_make_input("nope"), env)
        assert result.returncode == 1
        assert "Unknown action" in result.stderr

    def test_gws_not_installed(self):
        # Empty PATH — no gws binary anywhere
        result = _run_tool(_make_input("auth_status"), env={"PATH": ""})
        assert result.returncode == 1
        assert "gws CLI is not installed" in result.stderr

    def test_gws_failure(self, tmp_path):
        env = _make_gws_shim(tmp_path, """\
            #!/bin/sh
            echo "401 Unauthorized" >&2
            exit 1
        """)
        result = _run_tool(_make_input("auth_status"), env)
        assert result.returncode == 1
        assert "gws error" in result.stderr


# ---------------------------------------------------------------------------
# M9 — Malformed input
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_invalid_json(self, tmp_path):
        env = _make_gws_shim(tmp_path, "#!/bin/sh\necho ok")
        result = _run_tool(None, env, raw_stdin="not json")
        assert result.returncode == 1

    def test_missing_args_key(self, tmp_path):
        env = _make_gws_shim(tmp_path, "#!/bin/sh\necho ok")
        result = _run_tool(None, env, raw_stdin=json.dumps({}))
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# M10 — SIGTERM graceful shutdown
# ---------------------------------------------------------------------------

class TestSigterm:
    def test_sigterm_exits_cleanly(self, tmp_path):
        """Start run.py with a gws that sleeps; SIGTERM should cause clean exit 0."""
        env = _make_gws_shim(tmp_path, """\
            #!/bin/sh
            sleep 30
        """)
        process_env = {"PATH": f"{tmp_path}:{os.environ.get('PATH', '')}"}
        stdin_text = json.dumps(_make_input("auth_status"))

        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "run.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=process_env,
        )
        # Write stdin and close so main() can json.load
        proc.stdin.write(stdin_text)
        proc.stdin.close()

        # Wait a bit for process to start, then send SIGTERM
        time.sleep(0.5)
        proc.send_signal(signal.SIGTERM)

        # Should exit cleanly within a few seconds
        ret = proc.wait(timeout=5)
        assert ret == 0, f"Expected exit 0 after SIGTERM, got {ret}"

        # Verify no zombie — poll returns exit code (not None)
        assert proc.poll() is not None
