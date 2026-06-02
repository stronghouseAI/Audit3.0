import re
import json

class LocalPIIScrubber:
    def __init__(self, config_path: str = "config/scrubbing_rules.json"):
        try:
            with open(config_path, 'r') as f:
                # Read raw data and parse if content exists
                content = f.read().strip()
                config = json.loads(content) if content else {}
        except (FileNotFoundError, json.JSONDecodeError):
            # Safe runtime fallback if the file is missing, empty, or broken
            config = {}
            
        self.patterns = config.get("regex_patterns", {})
        self.agent_names = config.get("agent_names_fallback", [])

    def scrub(self, raw_text: str) -> str:
        scrubbed = raw_text
        for label, pattern in self.patterns.items():
            scrubbed = re.sub(pattern, f"[{label}_REDACTED]", scrubbed)
        
        for name in self.agent_names:
            scrubbed = re.sub(r'\b' + re.escape(name) + r'\b', "[AGENT_REDACTED]", scrubbed, flags=re.IGNORECASE)
            
        return scrubbed
