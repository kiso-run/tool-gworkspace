# tool-gworkspace — Development Plan

## Overview

Google Workspace tool for kiso. Wraps il CLI `gws`
(@googleworkspace/cli) per dare al planner accesso a Drive, Gmail,
Calendar, Sheets e qualsiasi altro servizio Workspace — tutto via
subprocess JSON stdin/stdout.

`gws` genera i comandi dinamicamente dal Discovery Service di Google,
quindi il tool espone sia azioni di alto livello (drive_list, gmail_send,
ecc.) sia un'azione `raw` per qualsiasi endpoint non coperto.

**Current status:** devplan — nessun codice ancora.

## Architecture

```
tool-gworkspace/
├── kiso.toml          # manifest: args schema, deps, usage guide
├── pyproject.toml     # Python deps (nessuna oltre stdlib)
├── run.py             # entry point + dispatch (~300 LOC target)
├── deps.sh            # installa gws via npm
├── tests/
│   ├── conftest.py    # shared fixtures, mock subprocess
│   ├── test_dispatch.py
│   └── test_actions.py
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
| auth_status      | Verifica se gws è autenticato                    | planned |
| drive_list       | Lista file in Drive (con query opzionale)        | planned |
| drive_read       | Scarica/leggi contenuto di un file               | planned |
| drive_upload     | Carica un file su Drive                          | planned |
| gmail_list       | Lista messaggi Gmail (con query opzionale)       | planned |
| gmail_read       | Leggi un messaggio specifico                     | planned |
| gmail_send       | Invia un'email                                   | planned |
| calendar_list    | Lista eventi di un calendario                    | planned |
| calendar_create  | Crea un evento nel calendario                    | planned |
| sheets_read      | Leggi dati da un foglio                          | planned |
| sheets_write     | Scrivi dati in un foglio                         | planned |
| raw              | Esegui qualsiasi comando gws arbitrario          | planned |

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

## Milestone Checklist

- [ ] **M1** — Scaffold + dispatch + raw action
- [ ] **M2** — Drive actions (list, read, upload)
- [ ] **M3** — Gmail actions (list, read, send)
- [ ] **M4** — Calendar actions (list, create)
- [ ] **M5** — Sheets actions (read, write)
- [ ] **M6** — Test suite + edge cases
- [ ] **M7** — Output formatting + planner UX

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
