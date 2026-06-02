# Asynchronous Compliance Audit Pipeline (Audit 3.0)

An enterprise-grade, asynchronous Python ETL pipeline designed to ingest bulk audio compliance files, evaluate them using the Gemini API structured outputs, and instantly dispatch high-priority alerts to stakeholders via Twilio WhatsApp.

## 🏗️ System Architecture

The system utilizes an asynchronous event-driven design to process binary payloads in parallel while enforcing strict data consistency and platform rate-limiting constraints.

## 🚀 Key Engineering Highlights

### 1. Concurrency Control & Rate-Limit Mitigation
To prevent hitting upstream `HTTP 429 (Too Many Requests)` rate walls from the Gemini API during bulk audio processing, the pipeline implements an asynchronous traffic-cop mechanism via `asyncio.Semaphore(2)`. This strictly bounds maximum concurrent network connections to exactly two workers, maximizing throughput without risking job execution failures.

### 2. Strict Type & Value Assertion (Pydantic Layer)
To eliminate data scaling anomalies (such as hallucinated percentage bounds or float drift), raw LLM responses are forced into strict integer validation blocks using Pydantic.
* **Constraint Enforcement:** Strict 1–10 integer data structures.
* **Data Guarantee:** Invalid or malformed response formats are caught at the edge before hitting any alerting or tracking layers.

### 3. Asynchronous Live-Alert Triggers
When an agent score drops below the defined threshold (< 8/10), the pipeline bypasses standard logging queues and hands off execution to a custom `notifier.py` module. This module hooks into the live Twilio WhatsApp session window, pushing free-form, markdown-formatted alerts straight to mobile devices for immediate human-in-the-loop intervention.

## 🛠️ Tech Stack & Environment

* **Runtime:** Python 3.10+ / `asyncio` core
* **Inference Engine:** Google Gemini API (Paid Tier)
* **Data Validation:** Pydantic v2
* **Notification Layer:** Twilio WhatsApp Gateway API
* **Host Environment:** Ubuntu Linux (Targeted for x86_64 architecture)
