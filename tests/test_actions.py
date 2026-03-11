import json
from pathlib import Path

import pytest

from run import (
    _run_gws,
    _truncate,
    do_auth_status,
    do_raw,
    _format_drive_list,
    _format_calendar_list,
    _format_sheets_read,
)


class TestRunGws:
    def test_success(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="hello world")
        result = _run_gws("auth", "status")
        assert result == "hello world"

    def test_strips_whitespace(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="  result  \n")
        result = _run_gws("auth", "status")
        assert result == "result"

    def test_failure_stderr(self, mock_gws):
        _, respond = mock_gws
        respond(stderr="bad request", returncode=1)
        with pytest.raises(ValueError, match="gws error: bad request"):
            _run_gws("drive", "files", "list")

    def test_failure_stdout_fallback(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="error info", stderr="", returncode=1)
        with pytest.raises(ValueError, match="gws error: error info"):
            _run_gws("drive", "files", "list")

    def test_failure_unknown(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="", stderr="", returncode=1)
        with pytest.raises(ValueError, match="gws error: unknown error"):
            _run_gws("fail")


class TestTruncate:
    def test_short_text(self):
        assert _truncate("hello") == "hello"

    def test_long_text(self):
        text = "x" * 5000
        result = _truncate(text)
        assert len(result) < 5000
        assert result.endswith("... (output truncated)")


class TestAuthStatus:
    def test_returns_gws_output(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="Authenticated as test@example.com")
        assert do_auth_status() == "Authenticated as test@example.com"


class TestRaw:
    def test_requires_command(self):
        with pytest.raises(ValueError, match="'command' argument is required"):
            do_raw({"command": ""})

    def test_executes_command(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout="result")
        assert do_raw({"command": "calendar events list"}) == "result"
        assert mock_run.call_args[0][0] == ["gws", "calendar", "events", "list"]

    def test_truncates_long_output(self, mock_gws):
        _, respond = mock_gws
        respond(stdout="x" * 5000)
        result = do_raw({"command": "something"})
        assert result.endswith("... (output truncated)")


class TestFormatDriveList:
    def test_empty(self):
        assert _format_drive_list('{"files": []}') == "No files found."

    def test_with_files(self):
        data = json.dumps({"files": [
            {"id": "abc123", "name": "doc.txt", "mimeType": "text/plain",
             "modifiedTime": "2025-01-01T00:00:00Z", "size": "1024"},
        ]})
        result = _format_drive_list(data)
        assert "doc.txt" in result
        assert "abc123" in result
        assert "1024 bytes" in result


class TestFormatCalendarList:
    def test_empty(self):
        assert _format_calendar_list('{"items": []}') == "No events found."

    def test_with_events(self):
        data = json.dumps({"items": [
            {"summary": "Meeting", "start": {"dateTime": "2025-01-01T10:00:00Z"},
             "end": {"dateTime": "2025-01-01T11:00:00Z"}, "location": "Room A"},
        ]})
        result = _format_calendar_list(data)
        assert "Meeting" in result
        assert "Room A" in result


class TestFormatSheetsRead:
    def test_empty(self):
        assert _format_sheets_read('{"values": []}') == "No data found."

    def test_with_data(self):
        data = json.dumps({"values": [["Name", "Age"], ["Alice", "30"]]})
        result = _format_sheets_read(data)
        assert "Name" in result
        assert "Alice" in result
        assert "|" in result
