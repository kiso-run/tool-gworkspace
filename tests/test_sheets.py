import json

import pytest

from run import do_sheets_read, do_sheets_write


class TestDoSheetsRead:
    def test_success(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({
            "values": [["Name", "Score"], ["Alice", "95"]],
        }))
        result = do_sheets_read({"spreadsheet_id": "sp1", "range": "Sheet1!A1:B2"})
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["spreadsheetId"] == "sp1"
        assert params["range"] == "Sheet1!A1:B2"
        assert "Name" in result
        assert "Alice" in result

    def test_missing_spreadsheet_id(self):
        with pytest.raises(ValueError, match="spreadsheet_id"):
            do_sheets_read({"spreadsheet_id": "", "range": "A1:B2"})

    def test_missing_range(self):
        with pytest.raises(ValueError, match="range"):
            do_sheets_read({"spreadsheet_id": "sp1", "range": ""})


class TestDoSheetsWrite:
    def test_success(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"updatedCells": 4}')
        result = do_sheets_write({
            "spreadsheet_id": "sp2",
            "range": "Sheet1!A1:B2",
            "values": '[["X", "Y"], ["1", "2"]]',
        })
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["spreadsheetId"] == "sp2"
        assert params["range"] == "Sheet1!A1:B2"
        assert params["valueInputOption"] == "USER_ENTERED"
        body = json.loads(call_args[call_args.index("--json") + 1])
        assert body["values"] == [["X", "Y"], ["1", "2"]]
        assert "Written to Sheet1!A1:B2" in result

    def test_missing_spreadsheet_id(self):
        with pytest.raises(ValueError, match="spreadsheet_id"):
            do_sheets_write({"spreadsheet_id": "", "range": "A1", "values": "[[1]]"})

    def test_missing_range(self):
        with pytest.raises(ValueError, match="range"):
            do_sheets_write({"spreadsheet_id": "sp1", "range": "", "values": "[[1]]"})

    def test_missing_values(self):
        with pytest.raises(ValueError, match="values"):
            do_sheets_write({"spreadsheet_id": "sp1", "range": "A1", "values": ""})

    def test_invalid_json_values(self):
        with pytest.raises(json.JSONDecodeError):
            do_sheets_write({
                "spreadsheet_id": "sp1",
                "range": "A1",
                "values": "not valid json",
            })
