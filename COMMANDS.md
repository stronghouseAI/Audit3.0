# Audit 3.0 — CLI Reference

> Enterprise Compliance Engine & Advanced Dev Assistant

---

## Global

```
audit --help
```

| Option | Description |
|--------|-------------|
| `--help` | Show help and exit. |
| `--version` | Show version and exit. |

---

## `audit sweep`

Execute a compliance audit over a directory of transcripts or audio files.

```
audit sweep --dir <PATH> [OPTIONS]
```

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--dir <PATH>` | `-d` | *(required)* | Directory containing `.txt` transcripts or `.mp3` audio files to audit. Must exist and be readable. |
| `--concurrency <INT>` | `-c` | `2` | Max simultaneous async cloud processing tasks. Ignored (forced to `1`) when `--local` is active. |
| `--region <STR>` | `-r` | `UK` | Regulatory compliance ruleset to apply. Accepted values: `UK`, `US`, `EU`. |
| `--local` / *(flag)* | `-l` | `False` | Run fully offline using the local GGUF model. Disables cloud API calls and enforces sequential processing. |
| `--csv` / `--no-csv` | — | `--csv` | Export `full_batch_audit_report.csv` to the project root on completion. Pass `--no-csv` to skip. |
| `--help` | — | — | Show help and exit. |

### Examples

```bash
# Standard cloud sweep with defaults
audit sweep --dir ./transcripts

# High-concurrency cloud sweep for a large batch
audit sweep --dir ./transcripts --concurrency 5

# Offline sweep using local model
audit sweep --dir ./transcripts --local

# EU compliance rules, no CSV export
audit sweep --dir ./transcripts --region EU --no-csv

# Full explicit run
audit sweep --dir /home/lippy/Documents/googleDev/Audit3.0/transcripts --concurrency 3 --region UK --csv
```

### Output

- Audit results are written to `audit_history.db` (SQLite).
- If `--csv` is active, a `full_batch_audit_report.csv` is saved to the project root.
- If compliance breaches are detected, a WhatsApp summary is dispatched via Twilio.

---

## `audit ask`

Send a one-shot question to Gemini 2.5 Flash directly from the terminal.

```
audit ask "<QUESTION>"
```

| Argument | Description |
|----------|-------------|
| `<QUESTION>` | Your development question or audit query (required, wrap in quotes). |
| `--help` | Show help and exit. |

### Examples

```bash
audit ask "What does a no-win-no-fee disclosure require under UK FCA rules?"
audit ask "Summarise the latest compliance checklist requirements"
```

> **Requires:** `GEMINI_API_KEY` environment variable to be set.

---

## `audit chat`

Open a continuous interactive chat session in the terminal.

```
audit chat [OPTIONS]
```

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--local` / *(flag)* | `-l` | `False` | Run the session fully offline using the local GGUF model. |
| `--help` | — | — | Show help and exit. |

### Examples

```bash
# Cloud-connected session
audit chat

# Fully offline session
audit chat --local
```

Type `exit` or `quit` to end the session.

---

## Environment Variables

| Variable | Required By | Description |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | `sweep`, `ask`, `chat` (cloud mode) | Google Gemini API key for cloud inference. |
| `TWILIO_ACCOUNT_SID` | `sweep` | Twilio account SID for WhatsApp breach notifications. |
| `TWILIO_AUTH_TOKEN` | `sweep` | Twilio auth token for WhatsApp breach notifications. |
