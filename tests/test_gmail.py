import base64
import json

import pytest

from run import do_gmail_list, do_gmail_read, do_gmail_send, _extract_gmail_body


class TestDoGmailList:
    def test_with_query(self, mock_gws):
        mock_run, respond = mock_gws
        # First call: list returns one message
        respond(stdout=json.dumps({"messages": [{"id": "m1", "threadId": "t1"}]}))
        # Second call: get metadata for m1
        respond(stdout=json.dumps({
            "payload": {"headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "alice@example.com"},
                {"name": "Date", "value": "2025-01-15"},
            ]},
        }))
        result = do_gmail_list({"query": "from:alice"})
        # Verify query was passed
        list_call = mock_run.call_args_list[0][0][0]
        params = json.loads(list_call[list_call.index("--params") + 1])
        assert params["q"] == "from:alice"
        assert "Hello" in result
        assert "alice@example.com" in result

    def test_without_query(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout=json.dumps({"messages": [{"id": "m2", "threadId": "t2"}]}))
        respond(stdout=json.dumps({
            "payload": {"headers": [
                {"name": "Subject", "value": "Test"},
                {"name": "From", "value": "bob@example.com"},
                {"name": "Date", "value": "2025-02-01"},
            ]},
        }))
        result = do_gmail_list({})
        list_call = mock_run.call_args_list[0][0][0]
        params = json.loads(list_call[list_call.index("--params") + 1])
        assert "q" not in params
        assert "Test" in result

    def test_no_messages(self, mock_gws):
        _, respond = mock_gws
        respond(stdout=json.dumps({"messages": []}))
        result = do_gmail_list({})
        assert result == "No messages found."

    def test_no_messages_key(self, mock_gws):
        _, respond = mock_gws
        respond(stdout=json.dumps({}))
        result = do_gmail_list({})
        assert result == "No messages found."

    def test_formats_headers_multiple_messages(self, mock_gws):
        _, respond = mock_gws
        respond(stdout=json.dumps({"messages": [
            {"id": "m1", "threadId": "t1"},
            {"id": "m2", "threadId": "t2"},
        ]}))
        # Headers for m1
        respond(stdout=json.dumps({
            "payload": {"headers": [
                {"name": "Subject", "value": "First"},
                {"name": "From", "value": "a@b.com"},
                {"name": "Date", "value": "2025-01-01"},
            ]},
        }))
        # Headers for m2
        respond(stdout=json.dumps({
            "payload": {"headers": [
                {"name": "Subject", "value": "Second"},
                {"name": "From", "value": "c@d.com"},
                {"name": "Date", "value": "2025-01-02"},
            ]},
        }))
        result = do_gmail_list({})
        assert "First" in result
        assert "Second" in result
        assert "[m1]" in result
        assert "[m2]" in result


class TestDoGmailRead:
    def test_success(self, mock_gws):
        _, respond = mock_gws
        body_data = base64.urlsafe_b64encode(b"Hello body").decode()
        respond(stdout=json.dumps({
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Date", "value": "2025-03-01"},
                    {"name": "Subject", "value": "Important"},
                ],
                "body": {"data": body_data},
            },
        }))
        result = do_gmail_read({"message_id": "msg123"})
        assert "From: sender@example.com" in result
        assert "To: me@example.com" in result
        assert "Subject: Important" in result
        assert "Hello body" in result

    def test_missing_message_id(self):
        with pytest.raises(ValueError, match="message_id"):
            do_gmail_read({"message_id": ""})


class TestExtractGmailBody:
    def test_plain_text(self):
        body_data = base64.urlsafe_b64encode(b"Plain text content").decode()
        payload = {
            "mimeType": "text/plain",
            "body": {"data": body_data},
        }
        assert _extract_gmail_body(payload) == "Plain text content"

    def test_nested_mime_parts_text_first(self):
        """text/plain part found when it comes before other parts."""
        body_data = base64.urlsafe_b64encode(b"Nested plain").decode()
        payload = {
            "mimeType": "multipart/alternative",
            "body": {},
            "parts": [
                {"mimeType": "text/plain", "body": {"data": body_data}},
                {"mimeType": "text/html", "body": {"data": "aHRtbA=="}},
            ],
        }
        assert _extract_gmail_body(payload) == "Nested plain"

    def test_deeply_nested_text_plain(self):
        """text/plain found inside a nested multipart."""
        body_data = base64.urlsafe_b64encode(b"Deep text").decode()
        payload = {
            "mimeType": "multipart/mixed",
            "body": {},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {},
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": body_data}},
                    ],
                },
            ],
        }
        assert _extract_gmail_body(payload) == "Deep text"

    def test_no_text_body_fallback(self):
        payload = {
            "mimeType": "multipart/mixed",
            "body": {},
            "parts": [
                {"mimeType": "text/html", "body": {"data": "aHRtbA=="}},
            ],
        }
        assert _extract_gmail_body(payload) == "(no text body)"


class TestDoGmailSend:
    def test_success(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"id": "sent1"}')
        result = do_gmail_send({
            "to": "recipient@example.com",
            "subject": "Test Subject",
            "body": "Test body text",
        })
        assert "Email sent to recipient@example.com" in result
        call_args = mock_run.call_args[0][0]
        assert "send" in call_args
        # Verify the raw message was base64-encoded
        json_arg = json.loads(call_args[call_args.index("--json") + 1])
        assert "raw" in json_arg

    def test_with_cc_bcc(self, mock_gws):
        mock_run, respond = mock_gws
        respond(stdout='{"id": "sent2"}')
        do_gmail_send({
            "to": "to@example.com",
            "subject": "CC Test",
            "body": "body",
            "cc": "cc@example.com",
            "bcc": "bcc@example.com",
        })
        # Decode the raw message to verify cc/bcc headers
        call_args = mock_run.call_args[0][0]
        json_arg = json.loads(call_args[call_args.index("--json") + 1])
        raw_bytes = base64.urlsafe_b64decode(json_arg["raw"])
        raw_str = raw_bytes.decode("utf-8", errors="replace")
        assert "cc@example.com" in raw_str
        assert "bcc@example.com" in raw_str

    def test_missing_to(self):
        with pytest.raises(ValueError, match="'to'"):
            do_gmail_send({"to": "", "subject": "s", "body": "b"})
