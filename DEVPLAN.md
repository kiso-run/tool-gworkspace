# tool-gworkspace — Development Plan

## Overview

Google Workspace tool for kiso. Wraps il CLI `gws`
(@googleworkspace/cli) per dare al planner accesso a Drive, Gmail,
Calendar, Sheets e qualsiasi altro servizio Workspace — tutto via
subprocess JSON stdin/stdout.

`gws` genera i comandi dinamicamente dal Discovery Service di Google,
quindi il tool espone sia azioni di alto livello (drive_list, gmail_send,
ecc.) sia un'azione `raw` per qualsiasi endpoint non coperto.

**Current status:** M1-M10 complete — full implementation with comprehensive test coverage + functional tests.

## Architecture

```
tool-gworkspace/
├── kiso.toml          # manifest: args schema, deps, usage guide
├── pyproject.toml     # Python deps (nessuna oltre stdlib)
├── run.py             # entry point + dispatch (~300 LOC target)
├── deps.sh            # installa gws via npm
├── tests/
│   ├── conftest.py      # shared fixtures, mock subprocess
│   ├── test_actions.py  # _run_gws, _truncate, auth_status, raw, formatters
│   ├── test_dispatch.py # dispatch routing, unknown action
│   ├── test_drive.py    # drive_list, drive_read, drive_upload
│   ├── test_gmail.py    # gmail_list, gmail_read, gmail_send, _extract_gmail_body
│   ├── test_calendar.py # calendar_list, calendar_create
│   └── test_sheets.py   # sheets_read, sheets_write
├── README.md
├── DEVPLAN.md
└── LICENSE
```

**Key design decisions:**

- Single-file `run.py` — coerente con tool-browser.
- Thin wrapper su `gws` — il tool non reimplementa le API Google, chiama
  `gws <service> <resource> <method>` via subprocess e ritorna il JSON.
- Auth via env var `GOOGLE_WORKSPACE_CLI_TOKEN` oppure credentials file
  in `~/.gws/` — il tool non gestisce il flusso OAuth interattivo.
- Azioni di alto livello per i casi più comuni + `raw` come escape hatch.
- Output JSON parsato e formattato in modo leggibile per il planner.

## Capabilities

| Action           | Description                                      | Status  |
|------------------|--------------------------------------------------|---------|
| auth_status      | Verifica se gws è autenticato                    | done    |
| drive_list       | Lista file in Drive (con query opzionale)        | done    |
| drive_read       | Scarica/leggi contenuto di un file               | done    |
| drive_upload     | Carica un file su Drive                          | done    |
| gmail_list       | Lista messaggi Gmail (con query opzionale)       | done    |
| gmail_read       | Leggi un messaggio specifico                     | done    |
| gmail_send       | Invia un'email                                   | done    |
| calendar_list    | Lista eventi di un calendario                    | done    |
| calendar_create  | Crea un evento nel calendario                    | done    |
| sheets_read      | Leggi dati da un foglio                          | done    |
| sheets_write     | Scrivi dati in un foglio                         | done    |
| raw              | Esegui qualsiasi comando gws arbitrario          | done    |

## Milestones

### M1 — Scaffold + dispatch + raw action

**Problem:** Il tool non esiste, serve la struttura base e un modo per
eseguire qualsiasi comando gws.

**Change:**
1. `pyproject.toml` — metadata, no deps extra (solo pytest per dev)
2. `kiso.toml` — manifest con args schema e usage guide
3. `run.py` — subprocess contract (JSON stdin → stdout/stderr):
   - `main()` legge JSON da stdin, chiama `dispatch()`
   - `dispatch()` route per action
   - `_run_gws(*args)` — chiama `gws` via `subprocess.run`, cattura
     stdout/stderr, parsa JSON output
   - `auth_status` — esegue `gws auth status`, ritorna stato
   - `raw` — accetta `command` (stringa con args gws), esegue e ritorna
4. `deps.sh` — `npm install -g @googleworkspace/cli`

**Test:**
- dispatch routing (unknown action → errore)
- `_run_gws` con mock subprocess
- `raw` con mock subprocess
- `auth_status` con mock subprocess

---

### M2 — Drive actions (list, read, upload)

**Problem:** Il planner non può accedere a Google Drive.

**Change:**
1. `drive_list(query?, page_size?)` →
   `gws drive files list --params '{"q": "...", "pageSize": N}'`
   - Formatta output: nome, id, mimeType, modifiedTime
2. `drive_read(file_id, format?)` →
   `gws drive files export` (per Google Docs) o
   `gws drive files get --params '{"alt": "media"}'` (per file binari)
   - Salva in `workspace/` e ritorna path + preview testo se possibile
3. `drive_upload(file_path, folder_id?, name?)` →
   `gws drive files create --upload <path> --json '{"name": "...", "parents": ["..."]}'`

**Test:**
- drive_list con/senza query, formattazione output
- drive_read per doc Google vs file binario
- drive_upload con/senza folder

---

### M3 — Gmail actions (list, read, send)

**Problem:** Il planner non può leggere o inviare email.

**Change:**
1. `gmail_list(query?, max_results?)` →
   `gws gmail users.messages list --params '{"userId": "me", "q": "...", "maxResults": N}'`
   - Per ogni messaggio, fetch headers (subject, from, date) con batch
2. `gmail_read(message_id)` →
   `gws gmail users.messages get --params '{"userId": "me", "id": "...", "format": "full"}'`
   - Estrai subject, from, to, date, body (text/plain preferito)
3. `gmail_send(to, subject, body, cc?, bcc?)` →
   `gws gmail users.messages send --json '{"raw": "<base64>"}'`
   - Costruisci RFC 2822 message, base64url encode

**Test:**
- gmail_list con/senza query
- gmail_read con parsing headers e body
- gmail_send con costruzione messaggio RFC 2822

---

### M4 — Calendar actions (list, create)

**Problem:** Il planner non può gestire il calendario.

**Change:**
1. `calendar_list(time_min?, time_max?, max_results?, calendar_id?)` →
   `gws calendar events list --params '{"calendarId": "primary", "timeMin": "...", ...}'`
   - Formatta: summary, start, end, location, attendees
2. `calendar_create(summary, start, end, description?, location?, attendees?, calendar_id?)` →
   `gws calendar events insert --params '{"calendarId": "primary"}' --json '{"summary": "...", ...}'`
   - Supporta date (all-day) e dateTime (con timezone)

**Test:**
- calendar_list con/senza filtri temporali
- calendar_create all-day vs timed event

---

### M5 — Sheets actions (read, write)

**Problem:** Il planner non può leggere/scrivere spreadsheet.

**Change:**
1. `sheets_read(spreadsheet_id, range)` →
   `gws sheets spreadsheets.values get --params '{"spreadsheetId": "...", "range": "..."}'`
   - Formatta come tabella leggibile
2. `sheets_write(spreadsheet_id, range, values)` →
   `gws sheets spreadsheets.values update --params '{"spreadsheetId": "...", "range": "...", "valueInputOption": "USER_ENTERED"}' --json '{"values": [...]}'`

**Test:**
- sheets_read formattazione tabella
- sheets_write con matrice valori

---

### M6 — Test suite + edge cases

**Problem:** Copertura test incompleta, mancano edge case.

**Change:**
1. Test per errori `gws` (non installato, non autenticato, API error)
2. Test per output troncato (risposte molto lunghe)
3. Test per parametri mancanti/invalidi su ogni action
4. `conftest.py` — fixture `mock_gws` che mocka `subprocess.run`

---

### M7 — Output formatting + planner UX

**Problem:** Output JSON grezzo è difficile da leggere per il planner.

**Change:**
1. Formattatore intelligente per ogni action:
   - drive_list → tabella con colonne allineate
   - gmail_list → lista con subject, from, date
   - calendar_list → timeline con orari
   - sheets_read → tabella ASCII
2. Troncamento automatico output > 4000 chars con nota "truncated"
3. Messaggi di errore user-friendly (non stack trace gws)

### M8 — Complete test coverage

**Problem:** Existing tests only covered `_run_gws`, `_truncate`, `auth_status`,
`raw`, dispatch routing, and formatters. All 13 action functions lacked dedicated
unit tests for their parameter handling, gws arg construction, and error paths.

**Change:**
1. `tests/test_drive.py` — `do_drive_list` (query/no-query/page_size/format),
   `do_drive_read` (success/export/get/missing file_id),
   `do_drive_upload` (success/folder_id/custom name/default name/missing path/nonexistent file)
2. `tests/test_gmail.py` — `do_gmail_list` (query/no-query/no messages/multiple messages),
   `do_gmail_read` (success/missing message_id),
   `_extract_gmail_body` (plain text/nested parts/no text fallback),
   `do_gmail_send` (success/cc+bcc/missing to)
3. `tests/test_calendar.py` — `do_calendar_list` (default calendar/time filters/custom calendar_id),
   `do_calendar_create` (timed/all-day/description+location+attendees/missing summary/start/end)
4. `tests/test_sheets.py` — `do_sheets_read` (success/missing spreadsheet_id/missing range),
   `do_sheets_write` (success/missing spreadsheet_id/range/values/invalid JSON)

**Test:** 69 tests total, all passing (was 24).

---

## Milestone Checklist

- [x] **M1** — Scaffold + dispatch + raw action
- [x] **M2** — Drive actions (list, read, upload)
- [x] **M3** — Gmail actions (list, read, send)
- [x] **M4** — Calendar actions (list, create)
- [x] **M5** — Sheets actions (read, write)
- [x] **M6** — Test suite + edge cases
- [x] **M7** — Output formatting + planner UX
- [x] **M8** — Complete test coverage

### M9 — Functional tests (subprocess contract)

**Problem:** All 69 tests are unit tests that call functions directly with
mocked `subprocess.run`. No test exercises the actual `main()` entry point
via the subprocess protocol (JSON on stdin → stdout/stderr + exit code).
The `run_tool` fixture exists in `conftest.py` but no test uses it.

**Files:** `tests/test_functional.py` (new)

**Change:**

Tests run `run.py` as a real subprocess via the `run_tool` fixture.
Since `gws` is not available in CI, mock it with a shell shim in `$PATH`.

1. **Happy path — raw action:**
   - stdin: `{args: {action: "raw", command: "auth status"}, ...}`
   - Mock gws shim prints `"Authenticated"`, exits 0
   - Assert: stdout contains `"Authenticated"`, exit code 0

2. **Happy path — drive_list action:**
   - Mock gws shim prints JSON `{files: [{id: "f1", name: "doc.txt", ...}]}`
   - Assert: stdout contains formatted file listing, exit code 0

3. **Error — missing action:**
   - stdin: `{args: {}, ...}` (no `action` key)
   - Assert: stderr contains `'action' argument is required`, exit code 1

4. **Error — unknown action:**
   - stdin: `{args: {action: "nope"}, ...}`
   - Assert: stderr contains `Unknown action`, exit code 1

5. **Error — gws not installed:**
   - Empty `$PATH` (no `gws` binary)
   - Assert: stderr contains `gws CLI is not installed`, exit code 1

6. **Error — gws returns failure:**
   - Mock gws shim exits 1 with stderr `"401 Unauthorized"`
   - Assert: stderr contains `gws error`, exit code 1

7. **Malformed input — invalid JSON on stdin:**
   - Send `"not json"` on stdin
   - Assert: exit code 1 (json.load raises)

8. **Malformed input — missing `args` key:**
   - stdin: `{}` (no `args`)
   - Assert: exit code 1 (KeyError on `data["args"]`)

- [x] Create mock gws shim fixture (shell script, chmod +x, prepend to PATH)
- [x] Implement all 8 functional tests
- [x] All tests pass (unit + functional)

---

### M10 — SIGTERM graceful shutdown test

**Problem:** `run.py` registers `signal.signal(signal.SIGTERM, ...)` for
graceful shutdown but no test verifies this behavior.

**Files:** `tests/test_functional.py` (add to existing)

**Change:**

1. Start `run.py` as subprocess with a gws shim that sleeps 10s
2. Send `SIGTERM` after 0.5s
3. Assert: process exits 0 (not killed, not stuck)
4. Assert: no zombie process left

- [x] Implement SIGTERM test
- [x] Passes on Linux (SIGTERM is POSIX)

---

## Milestone Checklist

- [x] **M1** — Scaffold + dispatch + raw action
- [x] **M2** — Drive actions (list, read, upload)
- [x] **M3** — Gmail actions (list, read, send)
- [x] **M4** — Calendar actions (list, create)
- [x] **M5** — Sheets actions (read, write)
- [x] **M6** — Test suite + edge cases
- [x] **M7** — Output formatting + planner UX
- [x] **M8** — Complete test coverage
- [x] **M9** — Functional tests (subprocess contract)
- [x] **M10** — SIGTERM graceful shutdown test
- [ ] **M11** — kiso.toml validation test
- [ ] **M12** — Security: command injection in raw action

### M11 — kiso.toml validation test

**Problem:** No test verifies that the `kiso.toml` manifest is valid and
consistent with the code — all declared args should be handled by `run.py`.

**Files:** `tests/test_manifest.py` (new)

**Change:**

1. Parse `kiso.toml` and extract all declared arg names from `[kiso.tool.args]`
2. Read `run.py` source and verify each declared arg appears in the code
   (via `args.get("arg_name")` or `args["arg_name"]`)
3. Verify `kiso.toml` is valid TOML
4. Verify required fields exist: `[kiso]` type, name, version, `[kiso.tool]` summary

- [ ] Implement manifest validation test
- [ ] All tests pass

---

### M12 — Security: command injection in raw action

**Problem:** `do_raw` uses `shlex.split(command)` which is safe against shell
injection, but no test verifies this. A test should confirm that shell
metacharacters in the `command` arg don't cause command injection.

**Files:** `tests/test_security.py` (new)

**Change:**

1. Call `do_raw({"command": "auth status; echo INJECTED"})` — verify the
   semicolon is treated as a literal arg to gws, not as shell injection
2. Call `do_raw({"command": "auth status && echo INJECTED"})` — same for &&
3. Call `do_raw({"command": "auth status $(echo INJECTED)"})` — same for $()
4. Verify `_run_gws` receives the full string as individual args (shlex splits correctly)

- [ ] Implement 3+ security tests
- [ ] All tests pass

---

## Known Issues / Improvement Ideas

- Auth flow interattivo non supportato — serve setup manuale di `gws auth`
  prima di usare il tool
- Nessun supporto per attachment Gmail (invio/download)
- Nessun supporto per Google Docs editing (solo read via export)
- Drive upload limitato a file nel workspace
- Nessun supporto per batch operations (es. spostare N file)
- Pagination automatica non esposta — usa `--page-all` di gws ma potrebbe
  generare output enormi
- Nessun caching locale dei risultati
