import pytest
from src.upstream.agent_a_scrubber import LocalPIIScrubber

def test_regex_and_agent_scrubbing(tmp_path):
    config_file = tmp_path / "test_rules.json"
    config_file.write_text("""
    {
      "regex_patterns": {
        "SSN": "\\\\b\\\\d{3}-\\\\d{2}-\\\\d{4}\\\\b"
      },
      "agent_names_fallback": ["Alice"]
    }
    """)
    
    scrubber = LocalPIIScrubber(config_path=str(config_file))
    raw_transcript = "Hello, my name is Alice and my SSN is 000-12-3456."
    expected = "Hello, my name is [AGENT_REDACTED] and my SSN is [SSN_REDACTED]."
    
    assert scrubber.scrub(raw_transcript) == expected
