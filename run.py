"""skill-gworkspace — Google Workspace automation via the gws CLI.

Subprocess contract (same as all kiso skills):
  stdin:  JSON {args, session, workspace, session_secrets, plan_outputs}
  stdout: result text on success
  stderr: error description on failure
  exit 0: success, exit 1: failure
"""
from __future__ import annotations

import json
import shlex
import shutil
import signal
import subprocess
import sys
from pathlib import Path

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_MAX_OUTPUT = 4000


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    data = json.load(sys.stdin)
    args = data["args"]
    workspace = Path(data.get("workspace", "/tmp"))
    action = args.get("action", "").strip()

    if not action:
        print("'action' argument is required", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("gws"):
        print(
            "gws CLI is not installed. "
            "Run: npm install -g @googleworkspace/cli",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result = dispatch(action, args, workspace)
        print(result)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(action: str, args: dict, workspace: Path) -> str:
    if action == "auth_status":
        return do_auth_status()
    if action == "raw":
        return do_raw(args)
    if action == "drive_list":
        return do_drive_list(args)
    if action == "drive_read":
        return do_drive_read(args, workspace)
    if action == "drive_upload":
        return do_drive_upload(args)
    if action == "gmail_list":
        return do_gmail_list(args)
    if action == "gmail_read":
        return do_gmail_read(args)
    if action == "gmail_send":
        return do_gmail_send(args)
    if action == "calendar_list":
        return do_calendar_list(args)
    if action == "calendar_create":
        return do_calendar_create(args)
    if action == "sheets_read":
        return do_sheets_read(args)
    if action == "sheets_write":
        return do_sheets_write(args)
    raise ValueError(
        f"Unknown action: {action!r}. "
        "Use: auth_status, drive_list, drive_read, drive_upload, "
        "gmail_list, gmail_read, gmail_send, calendar_list, calendar_create, "
        "sheets_read, sheets_write, raw"
    )


# ---------------------------------------------------------------------------
# gws runner
# ---------------------------------------------------------------------------

def _run_gws(*args: str) -> str:
    """Execute a gws command and return stdout. Raises ValueError on failure."""
    cmd = ["gws", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise ValueError(f"gws error: {err}")
    return result.stdout.strip()


def _truncate(text: str) -> str:
    """Truncate output if too long for the planner."""
    if len(text) <= _MAX_OUTPUT:
        return text
    return text[:_MAX_OUTPUT] + "\n\n... (output truncated)"


# ---------------------------------------------------------------------------
# Actions — M1: auth_status + raw
# ---------------------------------------------------------------------------

def do_auth_status() -> str:
    return _run_gws("auth", "status")


def do_raw(args: dict) -> str:
    command = args.get("command", "").strip()
    if not command:
        raise ValueError("raw: 'command' argument is required")
    parts = shlex.split(command)
    return _truncate(_run_gws(*parts))


# ---------------------------------------------------------------------------
# Actions — M2: Drive (stubs for dispatch routing)
# ---------------------------------------------------------------------------

def do_drive_list(args: dict) -> str:
    params: dict = {"pageSize": int(args.get("page_size", "10"))}
    query = args.get("query", "").strip()
    if query:
        params["q"] = query
    params["fields"] = "files(id,name,mimeType,modifiedTime,size)"
    raw = _run_gws("drive", "files", "list", "--params", json.dumps(params))
    return _format_drive_list(raw)


def do_drive_read(args: dict, workspace: Path) -> str:
    file_id = args.get("file_id", "").strip()
    if not file_id:
        raise ValueError("drive_read: 'file_id' argument is required")
    fmt = args.get("format", "").strip()
    if fmt:
        raw = _run_gws(
            "drive", "files", "export",
            "--params", json.dumps({"fileId": file_id, "mimeType": fmt}),
        )
    else:
        raw = _run_gws(
            "drive", "files", "get",
            "--params", json.dumps({"fileId": file_id, "alt": "media"}),
        )
    out_path = workspace / f"drive_{file_id}"
    out_path.write_text(raw, encoding="utf-8")
    preview = raw[:2000] if len(raw) > 2000 else raw
    return f"Saved to: {out_path}\n\n{preview}"


def do_drive_upload(args: dict) -> str:
    file_path = args.get("file_path", "").strip()
    if not file_path:
        raise ValueError("drive_upload: 'file_path' argument is required")
    if not Path(file_path).exists():
        raise ValueError(f"drive_upload: file not found: {file_path}")
    metadata: dict = {}
    name = args.get("name", "").strip()
    if name:
        metadata["name"] = name
    else:
        metadata["name"] = Path(file_path).name
    folder_id = args.get("folder_id", "").strip()
    if folder_id:
        metadata["parents"] = [folder_id]
    cmd_args = ["drive", "files", "create", "--upload", file_path]
    if metadata:
        cmd_args.extend(["--json", json.dumps(metadata)])
    return _truncate(_run_gws(*cmd_args))


# ---------------------------------------------------------------------------
# Actions — M3: Gmail
# ---------------------------------------------------------------------------

def do_gmail_list(args: dict) -> str:
    params: dict = {"userId": "me", "maxResults": int(args.get("page_size", "10"))}
    query = args.get("query", "").strip()
    if query:
        params["q"] = query
    raw = _run_gws("gmail", "users.messages", "list", "--params", json.dumps(params))
    data = json.loads(raw)
    messages = data.get("messages", [])
    if not messages:
        return "No messages found."
    lines = []
    for msg in messages:
        detail = _run_gws(
            "gmail", "users.messages", "get",
            "--params", json.dumps({
                "userId": "me", "id": msg["id"], "format": "metadata",
                "metadataHeaders": ["Subject", "From", "Date"],
            }),
        )
        info = json.loads(detail)
        headers = {h["name"]: h["value"] for h in info.get("payload", {}).get("headers", [])}
        lines.append(
            f"- [{msg['id']}] {headers.get('Date', '?')} | "
            f"{headers.get('From', '?')} | {headers.get('Subject', '(no subject)')}"
        )
    return _truncate("\n".join(lines))


def do_gmail_read(args: dict) -> str:
    message_id = args.get("message_id", "").strip()
    if not message_id:
        raise ValueError("gmail_read: 'message_id' argument is required")
    raw = _run_gws(
        "gmail", "users.messages", "get",
        "--params", json.dumps({"userId": "me", "id": message_id, "format": "full"}),
    )
    data = json.loads(raw)
    headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
    body_text = _extract_gmail_body(data.get("payload", {}))
    lines = [
        f"From: {headers.get('From', '?')}",
        f"To: {headers.get('To', '?')}",
        f"Date: {headers.get('Date', '?')}",
        f"Subject: {headers.get('Subject', '(no subject)')}",
        "",
        body_text,
    ]
    return _truncate("\n".join(lines))


def _extract_gmail_body(payload: dict) -> str:
    """Extract text/plain body from Gmail payload, recursing into parts."""
    import base64
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_gmail_body(part)
        if result:
            return result
    return "(no text body)"


def do_gmail_send(args: dict) -> str:
    to = args.get("to", "").strip()
    if not to:
        raise ValueError("gmail_send: 'to' argument is required")
    subject = args.get("subject", "").strip()
    body = args.get("body", "")
    import base64
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    cc = args.get("cc", "").strip()
    if cc:
        msg["Cc"] = cc
    bcc = args.get("bcc", "").strip()
    if bcc:
        msg["Bcc"] = bcc
    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    result = _run_gws(
        "gmail", "users.messages", "send",
        "--params", json.dumps({"userId": "me"}),
        "--json", json.dumps({"raw": raw_msg}),
    )
    return f"Email sent to {to}.\n{result}"


# ---------------------------------------------------------------------------
# Actions — M4: Calendar
# ---------------------------------------------------------------------------

def do_calendar_list(args: dict) -> str:
    cal_id = args.get("calendar_id", "").strip() or "primary"
    params: dict = {"calendarId": cal_id, "maxResults": int(args.get("page_size", "10"))}
    params["singleEvents"] = True
    params["orderBy"] = "startTime"
    time_min = args.get("time_min", "").strip()
    if time_min:
        params["timeMin"] = time_min
    time_max = args.get("time_max", "").strip()
    if time_max:
        params["timeMax"] = time_max
    raw = _run_gws("calendar", "events", "list", "--params", json.dumps(params))
    return _format_calendar_list(raw)


def do_calendar_create(args: dict) -> str:
    summary = args.get("summary", "").strip()
    if not summary:
        raise ValueError("calendar_create: 'summary' argument is required")
    start = args.get("start", "").strip()
    if not start:
        raise ValueError("calendar_create: 'start' argument is required")
    end = args.get("end", "").strip()
    if not end:
        raise ValueError("calendar_create: 'end' argument is required")
    cal_id = args.get("calendar_id", "").strip() or "primary"
    event: dict = {"summary": summary}
    # Detect all-day (YYYY-MM-DD) vs timed event
    if len(start) == 10:
        event["start"] = {"date": start}
        event["end"] = {"date": end}
    else:
        event["start"] = {"dateTime": start}
        event["end"] = {"dateTime": end}
    description = args.get("description", "").strip()
    if description:
        event["description"] = description
    location = args.get("location", "").strip()
    if location:
        event["location"] = location
    attendees = args.get("attendees", "").strip()
    if attendees:
        event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
    result = _run_gws(
        "calendar", "events", "insert",
        "--params", json.dumps({"calendarId": cal_id}),
        "--json", json.dumps(event),
    )
    return f"Event created: {summary}\n{result}"


# ---------------------------------------------------------------------------
# Actions — M5: Sheets
# ---------------------------------------------------------------------------

def do_sheets_read(args: dict) -> str:
    spreadsheet_id = args.get("spreadsheet_id", "").strip()
    if not spreadsheet_id:
        raise ValueError("sheets_read: 'spreadsheet_id' argument is required")
    range_ = args.get("range", "").strip()
    if not range_:
        raise ValueError("sheets_read: 'range' argument is required")
    raw = _run_gws(
        "sheets", "spreadsheets.values", "get",
        "--params", json.dumps({"spreadsheetId": spreadsheet_id, "range": range_}),
    )
    return _format_sheets_read(raw)


def do_sheets_write(args: dict) -> str:
    spreadsheet_id = args.get("spreadsheet_id", "").strip()
    if not spreadsheet_id:
        raise ValueError("sheets_write: 'spreadsheet_id' argument is required")
    range_ = args.get("range", "").strip()
    if not range_:
        raise ValueError("sheets_write: 'range' argument is required")
    values_str = args.get("values", "").strip()
    if not values_str:
        raise ValueError("sheets_write: 'values' argument is required")
    values = json.loads(values_str)
    result = _run_gws(
        "sheets", "spreadsheets.values", "update",
        "--params", json.dumps({
            "spreadsheetId": spreadsheet_id,
            "range": range_,
            "valueInputOption": "USER_ENTERED",
        }),
        "--json", json.dumps({"values": values}),
    )
    return f"Written to {range_}.\n{result}"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_drive_list(raw: str) -> str:
    data = json.loads(raw)
    files = data.get("files", [])
    if not files:
        return "No files found."
    lines = []
    for f in files:
        size = f.get("size", "")
        size_str = f" ({size} bytes)" if size else ""
        lines.append(
            f"- {f.get('name', '?')} [{f.get('id', '?')}] "
            f"({f.get('mimeType', '?')}) "
            f"modified: {f.get('modifiedTime', '?')}{size_str}"
        )
    return _truncate("\n".join(lines))


def _format_calendar_list(raw: str) -> str:
    data = json.loads(raw)
    items = data.get("items", [])
    if not items:
        return "No events found."
    lines = []
    for ev in items:
        start = ev.get("start", {})
        start_str = start.get("dateTime", start.get("date", "?"))
        end = ev.get("end", {})
        end_str = end.get("dateTime", end.get("date", "?"))
        loc = ev.get("location", "")
        loc_str = f" @ {loc}" if loc else ""
        lines.append(f"- {start_str} → {end_str} | {ev.get('summary', '(no title)')}{loc_str}")
    return _truncate("\n".join(lines))


def _format_sheets_read(raw: str) -> str:
    data = json.loads(raw)
    values = data.get("values", [])
    if not values:
        return "No data found."
    # Build ASCII table
    col_widths: list[int] = []
    for row in values:
        for i, cell in enumerate(row):
            w = len(str(cell))
            if i >= len(col_widths):
                col_widths.append(w)
            elif w > col_widths[i]:
                col_widths[i] = w
    lines = []
    for row in values:
        cells = []
        for i, cell in enumerate(row):
            width = col_widths[i] if i < len(col_widths) else 0
            cells.append(str(cell).ljust(width))
        lines.append(" | ".join(cells))
    return _truncate("\n".join(lines))


if __name__ == "__main__":
    main()
