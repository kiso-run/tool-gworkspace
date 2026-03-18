import json

import pytest

from run import do_calendar_list, do_calendar_create


class TestDoCalendarList:
    def test_default_calendar(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"items": [
            {"summary": "Standup", "start": {"dateTime": "2025-06-01T09:00:00Z"},
             "end": {"dateTime": "2025-06-01T09:30:00Z"}},
        ]}))
        result = do_calendar_list({})
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["calendarId"] == "primary"
        assert "Standup" in result

    def test_with_time_min_max(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"items": []}))
        do_calendar_list({
            "time_min": "2025-06-01T00:00:00Z",
            "time_max": "2025-06-30T23:59:59Z",
        })
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["timeMin"] == "2025-06-01T00:00:00Z"
        assert params["timeMax"] == "2025-06-30T23:59:59Z"

    def test_custom_calendar_id(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"items": []}))
        do_calendar_list({"calendar_id": "work@group.calendar.google.com"})
        call_args = mock_run.call_args[0][0]
        params = json.loads(call_args[call_args.index("--params") + 1])
        assert params["calendarId"] == "work@group.calendar.google.com"


class TestDoCalendarCreate:
    def test_timed_event(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"id": "ev1"}')
        result = do_calendar_create({
            "summary": "Meeting",
            "start": "2025-06-15T14:00:00Z",
            "end": "2025-06-15T15:00:00Z",
        })
        call_args = mock_run.call_args[0][0]
        event_json = json.loads(call_args[call_args.index("--json") + 1])
        assert event_json["start"] == {"dateTime": "2025-06-15T14:00:00Z"}
        assert event_json["end"] == {"dateTime": "2025-06-15T15:00:00Z"}
        assert "Event created: Meeting" in result

    def test_all_day_event(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"id": "ev2"}')
        result = do_calendar_create({
            "summary": "Holiday",
            "start": "2025-12-25",
            "end": "2025-12-26",
        })
        call_args = mock_run.call_args[0][0]
        event_json = json.loads(call_args[call_args.index("--json") + 1])
        assert event_json["start"] == {"date": "2025-12-25"}
        assert event_json["end"] == {"date": "2025-12-26"}
        assert "Event created: Holiday" in result

    def test_with_description_location_attendees(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"id": "ev3"}')
        do_calendar_create({
            "summary": "Workshop",
            "start": "2025-07-01T10:00:00Z",
            "end": "2025-07-01T12:00:00Z",
            "description": "Annual workshop",
            "location": "Conference Room B",
            "attendees": "alice@example.com, bob@example.com",
        })
        call_args = mock_run.call_args[0][0]
        event_json = json.loads(call_args[call_args.index("--json") + 1])
        assert event_json["description"] == "Annual workshop"
        assert event_json["location"] == "Conference Room B"
        assert event_json["attendees"] == [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ]

    def test_missing_summary(self):
        with pytest.raises(ValueError, match="summary"):
            do_calendar_create({"summary": "", "start": "2025-01-01", "end": "2025-01-02"})

    def test_missing_start(self):
        with pytest.raises(ValueError, match="start"):
            do_calendar_create({"summary": "Test", "start": "", "end": "2025-01-02"})

    def test_missing_end(self):
        with pytest.raises(ValueError, match="end"):
            do_calendar_create({"summary": "Test", "start": "2025-01-01", "end": ""})
