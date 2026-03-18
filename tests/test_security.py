import pytest
from run import do_raw

def test_semicolon_not_shell_injection(mock_gws):
    """shlex.split treats ; as literal, not shell metacharacter."""
    mock_run, respond = mock_gws
    respond(stdout="ok")
    do_raw({"command": "auth status; echo INJECTED"})
    # shlex.split("auth status; echo INJECTED") → ["auth", "status;", "echo", "INJECTED"]
    cmd = mock_run.call_args[0][0]
    assert cmd == ["gws", "auth", "status;", "echo", "INJECTED"]

def test_ampersand_not_shell_injection(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout="ok")
    do_raw({"command": "auth status && echo INJECTED"})
    cmd = mock_run.call_args[0][0]
    # && is treated as literal by shlex.split
    assert "&&" in cmd

def test_dollar_subst_not_shell_injection(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout="ok")
    do_raw({"command": 'auth status $(echo INJECTED)'})
    cmd = mock_run.call_args[0][0]
    # $() is treated as literal by shlex.split
    assert any("$(echo" in arg or "$(echo INJECTED)" in arg for arg in cmd)

def test_pipe_not_shell_injection(mock_gws):
    mock_run, respond = mock_gws
    respond(stdout="ok")
    do_raw({"command": "auth status | cat /etc/passwd"})
    cmd = mock_run.call_args[0][0]
    assert "|" in cmd
    assert cmd == ["gws", "auth", "status", "|", "cat", "/etc/passwd"]
