import json

import pytest

from run import do_drive_list, do_drive_read, do_drive_upload


class TestDoDriveList:
    def test_with_query(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"files": [
            {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf",
             "modifiedTime": "2025-06-01T12:00:00Z"},
        ]}))
        result = do_drive_list({"query": "name contains 'report'"})
        # Verify query was passed to gws
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["q"] == "name contains 'report'"
        assert "report.pdf" in result

    def test_without_query(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"files": []}))
        result = do_drive_list({})
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert "q" not in params
        assert result == "No files found."

    def test_custom_page_size(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"files": []}))
        do_drive_list({"page_size": "25"})
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["pageSize"] == 25

    def test_formats_output(self, mock_gws):
        _, respond = mock_gws
        respond(stdout=json.dumps({"files": [
            {"id": "abc", "name": "doc.txt", "mimeType": "text/plain",
             "modifiedTime": "2025-01-01T00:00:00Z", "size": "512"},
            {"id": "def", "name": "img.png", "mimeType": "image/png",
             "modifiedTime": "2025-02-01T00:00:00Z"},
        ]}))
        result = do_drive_list({})
        assert "doc.txt" in result
        assert "abc" in result
        assert "512 bytes" in result
        assert "img.png" in result
        assert "def" in result


class TestDoDriveRead:
    def test_success(self, mock_gws, tmp_path):
        _, respond = mock_gws
        respond(stdout="file content here")
        result = do_drive_read({"file_id": "abc123"}, workspace=tmp_path)
        assert "Saved to:" in result
        assert "file content here" in result
        saved = tmp_path / "drive_abc123"
        assert saved.exists()
        assert saved.read_text() == "file content here"

    def test_with_format_export(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        respond(stdout="exported content")
        result = do_drive_read(
            {"file_id": "xyz", "format": "text/csv"}, workspace=tmp_path,
        )
        call_args = mock_run.call_args[0][0]
        assert "export" in call_args
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["mimeType"] == "text/csv"
        assert "exported content" in result

    def test_without_format_uses_get(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        respond(stdout="binary-ish content")
        do_drive_read({"file_id": "xyz"}, workspace=tmp_path)
        call_args = mock_run.call_args[0][0]
        assert "get" in call_args
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["alt"] == "media"

    def test_missing_file_id(self):
        with pytest.raises(ValueError, match="file_id"):
            do_drive_read({"file_id": ""}, workspace=None)


class TestDoDriveUpload:
    def test_success(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        f = tmp_path / "upload.txt"
        f.write_text("hello")
        respond(stdout='{"id": "new123"}')
        result = do_drive_upload({"file_path": str(f)})
        call_args = mock_run.call_args[0][0]
        assert "--upload" in call_args
        assert str(f) in call_args
        assert "new123" in result

    def test_with_folder_id(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        f = tmp_path / "data.csv"
        f.write_text("a,b")
        respond(stdout='{"id": "u1"}')
        do_drive_upload({"file_path": str(f), "folder_id": "folder99"})
        call_args = mock_run.call_args[0][0]
        metadata = json.loads(call_args[call_args.index("--json") + 1])
        assert metadata["parents"] == ["folder99"]

    def test_with_custom_name(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        f = tmp_path / "data.csv"
        f.write_text("a,b")
        respond(stdout='{"id": "u2"}')
        do_drive_upload({"file_path": str(f), "name": "custom.csv"})
        call_args = mock_run.call_args[0][0]
        metadata = json.loads(call_args[call_args.index("--json") + 1])
        assert metadata["name"] == "custom.csv"

    def test_default_name_from_path(self, mock_gws, tmp_path):
        mock_run, respond = mock_gws
        f = tmp_path / "original.txt"
        f.write_text("x")
        respond(stdout='{"id": "u3"}')
        do_drive_upload({"file_path": str(f)})
        call_args = mock_run.call_args[0][0]
        metadata = json.loads(call_args[call_args.index("--json") + 1])
        assert metadata["name"] == "original.txt"

    def test_missing_file_path(self):
        with pytest.raises(ValueError, match="file_path"):
            do_drive_upload({"file_path": ""})

    def test_nonexistent_file(self):
        with pytest.raises(ValueError, match="file not found"):
            do_drive_upload({"file_path": "/nonexistent/path.txt"})
