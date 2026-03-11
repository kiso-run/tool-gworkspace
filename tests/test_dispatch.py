from pathlib import Path

import pytest

from run import dispatch


def test_unknown_action():
    with pytest.raises(ValueError, match="Unknown action"):
        dispatch("nonexistent", {"action": "nonexistent"}, Path("/tmp"))


def test_dispatch_auth_status(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout="Authenticated as user@example.com")
    result = dispatch("auth_status", {}, Path("/tmp"))
    assert "Authenticated" in result
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["gws", "auth", "status"]


def test_dispatch_raw_missing_command():
    with pytest.raises(ValueError, match="'command' argument is required"):
        dispatch("raw", {"command": ""}, Path("/tmp"))


def test_dispatch_raw_success(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout='{"files": []}')
    result = dispatch("raw", {"command": "drive files list"}, Path("/tmp"))
    assert '{"files": []}' in result
    assert mock_run.call_args[0][0] == ["gws", "drive", "files", "list"]


def test_dispatch_raw_with_quoted_args(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout="ok")
    dispatch("raw", {"command": 'drive files list --params \'{"pageSize": 5}\''}, Path("/tmp"))
    assert mock_run.call_args[0][0] == ["gws", "drive", "files", "list", "--params", '{"pageSize": 5}']


def test_dispatch_raw_gws_error(mock_gws):
    _, respond = mock_gws
    respond(stderr="401 Unauthorized", returncode=1)
    with pytest.raises(ValueError, match="gws error: 401 Unauthorized"):
        dispatch("raw", {"command": "drive files list"}, Path("/tmp"))


def test_dispatch_routes_all_actions(mock_gws):
    """Verify all high-level actions are routed (don't raise Unknown action)."""
    _, respond = mock_gws
    actions_requiring_args = {
        "drive_list": {},
        "gmail_list": {},
        "calendar_list": {},
    }
    for action, extra in actions_requiring_args.items():
        # Queue a response for each gws call
        respond(stdout='{"files":[],"messages":[],"items":[]}')
        args = {"action": action, **extra}
        # Should not raise ValueError("Unknown action")
        dispatch(action, args, Path("/tmp"))
