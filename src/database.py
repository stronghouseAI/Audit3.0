import sqlite3
import json
from pathlib import Path
from typing import TYPE_CHECKING

# Avoid circular imports if schemas are evaluated elsewhere, 
# while still providing type hinting support
if TYPE_CHECKING:
    from schemas import QAAuditReport

DB_PATH = Path(__file__).parent / "audit_history.db"

def init_db():
    """Initializes the SQLite database and creates tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Create Agents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            phone_number TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Create Audits Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_audits (
            audit_id TEXT PRIMARY KEY,
            agent_id TEXT,
            audio_filename TEXT,
            score INTEGER,
            justification TEXT,
            breach_detected INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
        )
    """)
    
    conn.commit()
    conn.close()

def save_audit_result(report: "QAAuditReport", phone_number: str = "UNKNOWN"):
    """
    Inserts or updates the agent and logs the structured Pydantic compliance audit result.
    Uses the audio filename string as the deterministic audit_id primary key.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        # 1. Upsert agent details (maintaining existing relational design)
        cursor.execute("""
            INSERT INTO agents (agent_id, phone_number)
            VALUES (?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET phone_number=excluded.phone_number
        """, (report.agent_id, phone_number))
        
        # 2. Package the Pydantic structural payload for the justification blob
        # This encapsulates the executive summary and structured violations without altering the table rows
        justification_payload = {
            "executive_summary": report.executive_summary,
            "detected_violations": [v.model_dump() for v in report.detected_violations]
        }
        justification_blob = json.dumps(justification_payload)
        
        # 3. Handle data metrics via an automated INSERT OR REPLACE upsert pattern
        # Breach is flipped if the structured contract explicitly flags a failed run
        breach = 0 if report.passed else 1
        
        cursor.execute("""
            INSERT OR REPLACE INTO compliance_audits (
                audit_id, agent_id, audio_filename, score, justification, breach_detected
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report.filename,       # audit_id
            report.agent_id,       # agent_id
            report.filename,       # audio_filename
            report.evaluation.score,  # score (1-10 scale)
            justification_blob,    # serialized structural verification
            breach                 # breach_detected status flag
        ))
        
        conn.commit()
    except Exception as e:
        print(f"[-] Database insertion error for {report.filename}: {e}")
        conn.rollback()
    finally:
        conn.close()

# Initialize tables immediately on module execution
init_db()
