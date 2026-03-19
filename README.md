# tool-gworkspace

Google Workspace automation via the gws CLI. Access Drive, Gmail, Calendar, Sheets, and any other Workspace API.

## Installation

```bash
kiso tool install gworkspace
```

This installs Python dependencies and the `gws` CLI (`@googleworkspace/cli`).

## Setup

The gws CLI must be authenticated before use:

```bash
gws auth setup
gws auth login
```

## Actions

| Action | Description |
|--------|-------------|
| `auth_status` | Check if gws is authenticated. |
| `drive_list` | List files in Google Drive. Optional `query` filter. |
| `drive_read` | Download/read a file from Drive. Requires `file_id`. |
| `drive_upload` | Upload a file to Drive. Requires `file_path`. Optional `folder_id`, `name`. |
| `gmail_list` | List Gmail messages. Optional `query` filter. |
| `gmail_read` | Read a specific Gmail message. Requires `message_id`. |
| `gmail_send` | Send an email. Requires `to`, `subject`, `body`. Optional `cc`, `bcc`. |
| `calendar_list` | List calendar events. Optional `time_min`, `time_max`. |
| `calendar_create` | Create a calendar event. Requires `summary`, `start`, `end`. |
| `sheets_read` | Read data from a spreadsheet. Requires `spreadsheet_id`, `range`. |
| `sheets_write` | Write data to a spreadsheet. Requires `spreadsheet_id`, `range`, `values`. |
| `raw` | Run any arbitrary gws command. Requires `command`. |

## Workflow

1. Use `auth_status` to verify authentication.
2. Use high-level actions (`drive_list`, `gmail_send`, etc.) for common tasks.
3. Use `raw` for any Workspace API not covered by the above actions.

## License

MIT
