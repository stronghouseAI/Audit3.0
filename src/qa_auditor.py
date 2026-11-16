import os
import csv
import glob
import asyncio
import json
import logging
from typing import List, Optional
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field, field_validator
from database import save_audit_result

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

# ==========================================
# CONFIGURATION
# ==========================================
LOCAL_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "supergemma4-26b-q4.gguf"
PASS_SCORE_THRESHOLD = 8
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
SCRIPT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "script_rules.json"


def load_script_rules(path: Path = SCRIPT_RULES_PATH) -> dict:
    """Load the agent-script compliance checklist from config/script_rules.json."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("rules"):
        raise ValueError(f"No rules defined in {path}")
    return data

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 🔒 MUTEX LOCK: Prevents concurrent worker threads from locking the SQLite database file
db_write_lock = asyncio.Lock()


# ==========================================
# STEP 1: ENFORCED SCHEMAS
# ==========================================
class ChecklistItem(BaseModel):
    requirement: str = Field(description="The name of the rule")
    status: str = Field(description="Must be exactly: PASS or FAIL")
    evidence: str = Field(description="Verbatim quote from the transcript as proof.")


class PhraseAnalysis(BaseModel):
    mandatory_phrases_found: List[str]
    mandatory_phrases_missing: List[str]
    prohibited_language_or_errors: List[str]


class CompetenceEvaluation(BaseModel):
    score: int = Field(description="A strict integer score from 1 to 10. NEVER use a 100-point scale.")
    justification: str
    improvement_suggestions: List[str]

    @field_validator('score')
    @classmethod
    def validate_score_bounds(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError(f"Score must be between 1 and 10, got {v}. Do not use a 100-point scale.")
        return v


class DetectedViolation(BaseModel):
    requirement: str
    status: str = "FAIL"
    evidence: str


class QAAuditReport(BaseModel):
    compliance_checklist: List[ChecklistItem]
    phrase_analysis: PhraseAnalysis
    evaluation: CompetenceEvaluation
    agent_name: str = Field(
        default="",
        description="The agent's name as they introduce themselves on the call, or empty if not stated.",
    )
    transcript: str = Field(
        default="",
        description="Full verbatim transcript of the call, one line per turn, prefixed 'Agent:' or 'Customer:'.",
    )

    # Database metadata fields — populated after LLM response
    filename: Optional[str] = None
    agent_id: Optional[str] = None
    executive_summary: Optional[str] = None
    detected_violations: List[DetectedViolation] = []
    passed: Optional[bool] = None


def _make_error_report(filename: str, agent_id: str, reason: str) -> QAAuditReport:
    """Build a minimal failed QAAuditReport for error states conforming to structural schemas."""
    return QAAuditReport(
        compliance_checklist=[],
        phrase_analysis=PhraseAnalysis(
            mandatory_phrases_found=[],
            mandatory_phrases_missing=[],
            prohibited_language_or_errors=[],
        ),
        evaluation=CompetenceEvaluation(
            score=1,
            justification=reason,
            improvement_suggestions=[],
        ),
        filename=filename,
        agent_id=agent_id,
        executive_summary=reason,
        detected_violations=[],
        passed=False,
    )


AUDIO_EXTENSIONS = (".mp3", ".mpeg", ".mp3.mpeg", ".wav", ".m4a")


def _parse_agent_info(filename: str) -> tuple[str, str, str]:
    """
    Extract agent_id, phone_number, and call_timestamp from a filename.
    Supports:
      - Agent0034_+447411873468_20260526134815_37d9bc.mp3
      - 20261113-115032_7787536564-all.mp3.mpeg   (dialler export: timestamp_phone)
      - 20261113122744_442045208806_07853844677-all.mp3.mpeg
    """
    base_name = Path(filename).name.split('.')[0]
    if base_name.endswith('-all'):
        base_name = base_name[:-4]
    parts = [p for p in base_name.split('_') if p]

    if parts and len(parts[0]) >= 8 and parts[0][:8].isdigit():
        # Dialler format: no agent in filename (agent name is taken from the call itself)
        call_timestamp = parts[0]
        phone_number = parts[-1] if len(parts) > 1 else "Unknown_Phone"
        return "Unknown_Agent", phone_number, call_timestamp

    agent_id = parts[0] if parts else "Unknown_Agent"
    phone_number = parts[1] if len(parts) > 1 else "Unknown_Phone"
    call_timestamp = parts[2] if len(parts) > 2 else "Unknown_Timestamp"
    return agent_id, phone_number, call_timestamp


def _extract_report_from_response(response) -> QAAuditReport:
    """
    Reliably extract a QAAuditReport from a Gemini response object.
    Prefers response.parsed (native Pydantic), falls back to response.text JSON.
    """
    if hasattr(response, 'parsed') and isinstance(response.parsed, QAAuditReport):
        return response.parsed

    raw_str = getattr(response, 'text', None) or str(response)

    raw_str = raw_str.strip()
    if raw_str.startswith("```"):
        raw_str = raw_str.split("```", 2)[-1 if raw_str.startswith("```json") else 1]
        raw_str = raw_str.rsplit("```", 1)[0].strip()

    if not raw_str:
        raise ValueError("Empty response body from Gemini — cannot parse audit report.")

    return QAAuditReport.model_validate_json(raw_str)


def _populate_report_metadata(report: QAAuditReport, filename: str, agent_id: str) -> QAAuditReport:
    """Enrich a raw LLM report with file-level metadata and derived fields."""
    report.filename = filename
    report.agent_id = agent_id
    report.executive_summary = report.evaluation.justification

    report.detected_violations = [
        DetectedViolation(requirement=item.requirement, evidence=item.evidence)
        for item in report.compliance_checklist
        if item.status == "FAIL"
    ]

    report.passed = (
        report.evaluation.score >= PASS_SCORE_THRESHOLD
        and len(report.detected_violations) == 0
    )

    return report


async def _safe_delete_file(client, audio_file) -> None:
    """Best-effort delete of a Gemini uploaded file; logs but never raises."""
    if audio_file is None:
        return
    try:
        await client.aio.files.delete(name=audio_file.name)
    except Exception as exc:
        logger.warning("Could not delete uploaded Gemini file %s: %s", audio_file.name, exc)


def _export_local_transcript_txt(input_folder: str, filename: str, agent_id: str, phone_number: str, timestamp: str, report: QAAuditReport) -> None:
    """
    Generates a localized, highly verbose sentence-by-sentence text audit report
    mapping metadata fields and verification evidence explicitly line-by-line.
    Saves the output securely into a dedicated subfolder within transcripts.
    """
    try:
        output_subfolder = Path(input_folder) / "audit_outputs"
        output_subfolder.mkdir(parents=True, exist_ok=True)
        
        txt_filename = output_subfolder / f"{Path(filename).name.split('.')[0]}.txt"
        
        if report.transcript:
            transcript_file = output_subfolder / f"{Path(filename).name.split('.')[0]}_transcript.txt"
            transcript_file.write_text(report.transcript, encoding="utf-8")

        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(f"=========================================================================\n")
            f.write(f"⚖️ CORPORATE AUDIT VERBOSE RECORD FOR: {filename}\n")
            f.write(f"=========================================================================\n")
            f.write(f"• AGENT IDENTIFIER: {agent_id}\n")
            f.write(f"• CUSTOMER MOBILE: {phone_number}\n")
            f.write(f"• CALL TIMESTAMP:   {timestamp}\n")
            f.write(f"• PIPELINE STATUS:  {'PASSED COMPLIANCE' if report.passed else 'CRITICAL BREACH DETECTED'}\n")
            f.write(f"• AUDIT SCORE:      {report.evaluation.score} / 10\n")
            f.write(f"-------------------------------------------------------------------------\n\n")
            
            f.write(f"📝 EXECUTIVE JUSTIFICATION SUMMARY:\n")
            f.write(f"{report.evaluation.justification}\n\n")
            
            f.write(f"📋 VERBOSE REQ-BY-REQ COMPLIANCE CHECKLIST EVIDENCE:\n")
            if report.compliance_checklist:
                for idx, item in enumerate(report.compliance_checklist, 1):
                    f.write(f"Line {idx:02d}: [{item.status}] Requirement: {item.requirement}\n")
                    clean_evidence = item.evidence.replace('\n', ' ').strip()
                    f.write(f"         Verbatim Evidence Quote: \"{clean_evidence if clean_evidence else 'None Documented'}\"\n")
            else:
                f.write("No active checklist requirements processed due to exception failure state.\n")
                
            f.write(f"\n💡 AGENT IMPROVEMENT RECOMMENDATIONS:\n")
            if report.evaluation.improvement_suggestions:
                for idx, suggestion in enumerate(report.evaluation.improvement_suggestions, 1):
                    f.write(f"• Suggestion {idx}: {suggestion}\n")
            else:
                f.write("• No professional adjustments required for this file.\n")
                
            if report.transcript:
                f.write(f"\n📞 FULL CALL TRANSCRIPT:\n{report.transcript}\n")

            f.write(f"\n=========================================================================\n")
            f.write(f"END OF DATA RECORD\n")
            
        logger.info("📄 Local verbose transcript artifact generated: %s", txt_filename)
    except Exception as e:
        logger.warning("Failed to output local transcript text document file block: %s", e)


# ==========================================
# STEP 2: ASYNC THROTTLED WORKER WITH RETRY
# ==========================================
async def audit_single_file_with_retry(
    client,
    filename: str,
    input_folder: str,
    system_instruction: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    use_local: bool = False,
    local_llm=None,
) -> dict:
    full_path = os.path.join(input_folder, filename)
    agent_id, phone_number, call_timestamp = _parse_agent_info(filename)
    is_text_file = filename.lower().endswith('.txt')

    async with semaphore:
        for attempt in range(1, max_retries + 1):
            audio_file = None
            try:
                logger.info(
                    "[Queue] Processing: %s (Attempt %d/%d) via %s",
                    filename, attempt, max_retries, "LOCAL" if use_local else "CLOUD",
                )

                # ---- Prepare payload ----
                if is_text_file:
                    with open(full_path, "r", encoding="utf-8") as f:
                        payload_content = f.read()
                    media_context = [
                        payload_content,
                        "Perform a complete linguistic compliance audit on this transcript.",
                    ]
                else:
                    if use_local:
                        raise ValueError(
                            f"Local pipeline cannot process binary files ({filename}). "
                            "Pre-convert to .txt first."
                        )
                    audio_file = await client.aio.files.upload(
                        file=full_path, config=types.UploadFileConfig(mime_type="audio/mpeg")
                    )
                    while audio_file.state.name == "PROCESSING":
                        await asyncio.sleep(3)
                        audio_file = await client.aio.files.get(name=audio_file.name)
                    if audio_file.state.name == "FAILED":
                        raise ValueError(f"Gemini file upload failed for: {filename}")
                    media_context = [
                        audio_file,
                        "Transcribe this call in full (populate the transcript field), then perform a complete linguistic compliance audit on it.",
                    ]
                    payload_content = None

                # ---- Run inference ----
                if use_local:
                    if local_llm is None:
                        raise ValueError("Local pipeline active but LLM instance is None.")

                    local_prompt = (
                        f"SYSTEM INSTRUCTIONS:\n{system_instruction}\n"
                        f"{'─' * 40}\n"
                        f"TASK: Audit the following transcript:\n\n{payload_content}"
                    )
                    response_raw = await asyncio.to_thread(
                        local_llm.create_chat_completion,
                        messages=[{"role": "user", "content": local_prompt}],
                        response_format={
                            "type": "json_object",
                            "schema": QAAuditReport.model_json_schema(),
                        },
                        temperature=0.0,
                    )
                    raw_text = response_raw["choices"][0]["message"]["content"]
                    report = QAAuditReport.model_validate_json(raw_text)

                else:
                    response = await client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=media_context,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.0,
                            response_mime_type="application/json",
                            response_schema=QAAuditReport,
                        ),
                    )
                    report = _extract_report_from_response(response)

                # ---- Enrich & save ----
                await _safe_delete_file(client, audio_file)
                if agent_id == "Unknown_Agent" and report.agent_name.strip():
                    agent_id = report.agent_name.strip()
                report = _populate_report_metadata(report, filename, agent_id)

                # 🛠️ EXECUTE LOCAL TXT EXPORT
                _export_local_transcript_txt(input_folder, filename, agent_id, phone_number, call_timestamp, report)

                logger.info("✅ COMPLETED: %s → Score %d/10 | Pass=%s", filename, report.evaluation.score, report.passed)

                # 🔒 Safe Single-Threaded Database Pipeline Lock
                async with db_write_lock:
                    await asyncio.to_thread(save_audit_result, report, phone_number)

                return {
                    "status": "SUCCESS",
                    "filename": filename,
                    "score": report.evaluation.score,
                    "breaches": [v.requirement for v in report.detected_violations],
                    "agent_id": agent_id,
                    "phone_number": phone_number,
                    "call_timestamp": call_timestamp,
                    "passed": report.passed,
                    "summary": report.evaluation.justification,
                    "improvements": report.evaluation.improvement_suggestions,
                }

            except APIError as exc:
                await _safe_delete_file(client, audio_file)
                if exc.code in (429, 503) and attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning("Rate limit (%s) for %s. Retrying in %ds…", exc.code, filename, wait_time)
                    await asyncio.sleep(wait_time)
                    continue
                reason = f"API_ERROR_{exc.code}"
                logger.error("Fatal API error on %s: %s", filename, exc)
                error_report = _make_error_report(filename, agent_id, reason)
                async with db_write_lock:
                    await asyncio.to_thread(save_audit_result, error_report, phone_number)
                return {"status": "FAILED", "filename": filename, "reason": reason,
                        "agent_id": agent_id, "phone_number": phone_number, "call_timestamp": call_timestamp}

            except Exception as exc:
                await _safe_delete_file(client, audio_file)
                reason = f"APP_ERROR: {exc}"
                logger.exception("Unexpected error processing %s", filename)
                error_report = _make_error_report(filename, agent_id, reason)
                async with db_write_lock:
                    await asyncio.to_thread(save_audit_result, error_report, phone_number)
                return {"status": "FAILED", "filename": filename, "reason": reason,
                        "agent_id": agent_id, "phone_number": phone_number, "call_timestamp": call_timestamp}


# ==========================================
# STEP 3: BATCH COORDINATOR
# ==========================================
async def main(
    target_dir: Optional[str] = None,
    max_concurrency: int = 2,
    auto_export: bool = True,
    use_local: bool = False,
    region: str = "UK",
) -> None:
    client = None
    local_llm = None

    if not use_local:
        if not os.environ.get("GEMINI_API_KEY"):
            logger.error("Environment variable 'GEMINI_API_KEY' is missing.")
            return
        client = genai.Client()
    else:
        logger.info("Loading local GGUF model into memory…")
        if Llama is None:
            raise ImportError("llama-cpp-python is not installed.")
        if not LOCAL_MODEL_PATH.exists():
            raise FileNotFoundError(f"GGUF model not found at: {LOCAL_MODEL_PATH}")
        local_llm = Llama(
            model_path=str(LOCAL_MODEL_PATH),
            n_ctx=2048,
            n_gpu_layers=20,
            n_threads=4,
        )

    input_folder = str(target_dir) if target_dir else "transcripts"
    if not os.path.exists(input_folder):
        logger.error("Target directory '%s' does not exist.", input_folder)
        return

    # 📂 DEFENSIVE TRANSCRIPT INGESTION GUARD: Explicitly ignores the nested output folder contents
    target_files = [
        os.path.basename(f)
        for f in glob.glob(os.path.join(input_folder, "*.txt"))
        if not os.path.basename(f).startswith('.') and "audit_outputs" not in f
    ]
    if not target_files:
        target_files = [
            os.path.basename(f)
            for f in glob.glob(os.path.join(input_folder, "*"))
            if f.lower().endswith(AUDIO_EXTENSIONS) and not os.path.basename(f).startswith('.')
        ]
    if not target_files:
        logger.info("No .txt or .mp3 files found in: %s", input_folder)
        return

    if use_local:
        logger.warning("Local mode: enforcing sequential processing (concurrency=1).")
        max_concurrency = 1

    semaphore = asyncio.Semaphore(max_concurrency)
    logger.info("Using Gemini model: %s", GEMINI_MODEL)
    logger.info(
        "Starting audit [Local=%s | Region=%s] on %d files. Concurrency: %d",
        use_local, region, len(target_files), max_concurrency,
    )

    script = load_script_rules()
    checklist = "\n".join(f"    {i}. {rule}" for i, rule in enumerate(script["rules"], 1))
    logger.info("Auditing against script: %s (%d rules)", script.get("script_name", "unnamed"), len(script["rules"]))

    SYSTEM_INSTRUCTION = f"""
    You are an Expert Quality Assurance Auditor specialising in linguistic analysis and compliance.
    Audit the provided content against regional regulatory rules [Target Zone: {region}].

    Required compliance checklist (one checklist item per rule, using the rule name as the requirement):
{checklist}

    If the input is audio, include a full verbatim transcript in the transcript field.
    Put the agent's name (as they introduce themselves) in the agent_name field.
    CRITICAL: The evaluation score must be an integer from 1 to 10. Never use a 100-point scale.
    """

    tasks = [
        audit_single_file_with_retry(
            client, filename, input_folder, SYSTEM_INSTRUCTION,
            semaphore, use_local=use_local, local_llm=local_llm,
        )
        for filename in target_files
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All files processed.")

    total_audited = 0
    total_breaches = 0
    low_performing_agents: List[str] = []

    for res in results:
        if isinstance(res, dict) and res.get("status") == "SUCCESS":
            total_audited += 1
            if res["score"] < PASS_SCORE_THRESHOLD:
                total_breaches += 1
                low_performing_agents.append(f"{res['agent_id']} (Score: {res['score']})")

    logger.info("%d file(s) audited, %d below pass threshold: %s",
                total_audited, total_breaches, ", ".join(low_performing_agents) or "none")

    if auto_export:
        csv_path = Path(input_folder) / "audit_outputs" / "full_batch_audit_report.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        headers = ["Agent ID", "Phone Number", "Call Timestamp", "Audio Filename", "Status",
                   "Score (1-10)", "Result", "Failed Requirements", "Summary", "Improvements"]
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            for res in results:
                if not isinstance(res, dict):
                    continue
                ok = res.get("status") == "SUCCESS"
                writer.writerow([
                    res.get("agent_id", ""), res.get("phone_number", ""), res.get("call_timestamp", ""),
                    res.get("filename", ""), res.get("status", ""),
                    res.get("score", "") if ok else "",
                    ("PASS" if res.get("passed") else "FAIL") if ok else "ERROR",
                    "; ".join(res.get("breaches", [])),
                    res.get("summary", "") if ok else res.get("reason", ""),
                    "; ".join(res.get("improvements", [])),
                ])
        logger.info("CSV batch report saved: %s", csv_path)

if __name__ == "__main__":
    asyncio.run(main())
