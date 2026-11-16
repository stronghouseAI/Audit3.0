# Asynchronous Compliance Audit Pipeline (Audit 3.0)

An enterprise-grade, asynchronous Python ETL pipeline designed to ingest bulk audio compliance files, evaluate them using the Gemini API structured outputs, transcribe each call, and export per-call audit reports plus a batch CSV.

## 🏗️ System Architecture

The system utilizes an asynchronous event-driven design to process binary payloads in parallel while enforcing strict data consistency and platform rate-limiting constraints.

## 🚀 Key Engineering Highlights

### 1. Concurrency Control & Rate-Limit Mitigation
To prevent hitting upstream `HTTP 429 (Too Many Requests)` rate walls from the Gemini API during bulk audio processing, the pipeline implements an asynchronous traffic-cop mechanism via `asyncio.Semaphore(2)`. This strictly bounds maximum concurrent network connections to exactly two workers, maximizing throughput without risking job execution failures.

### 2. Strict Type & Value Assertion (Pydantic Layer)
To eliminate data scaling anomalies (such as hallucinated percentage bounds or float drift), raw LLM responses are forced into strict integer validation blocks using Pydantic.
* **Constraint Enforcement:** Strict 1–10 integer data structures.
* **Data Guarantee:** Invalid or malformed response formats are caught at the edge before hitting any alerting or tracking layers.

### 3. Editable Script Rules
The compliance checklist lives in `config/script_rules.json`. When the agent script changes, edit the `rules` list there; no code changes needed.

### 4. Outputs
For every call, `<dir>/audit_outputs/` gets a full audit report (`<name>.txt`) and, for MP3s, the full transcript (`<name>_transcript.txt`). A batch summary is written to `<dir>/audit_outputs/full_batch_audit_report.csv`.

## 🛠️ Tech Stack & Environment

* **Runtime:** Python 3.10+ / `asyncio` core
* **Inference Engine:** Google Gemini API (Paid Tier)
* **Data Validation:** Pydantic v2
* **Host Environment:** Ubuntu Linux (Targeted for x86_64 architecture)
