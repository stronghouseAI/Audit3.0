import json
import os

class DynamicContextInjector:
    def __init__(self, manifest_path: str = "config/regional_manifest.json", manuals_dir: str = "regulatory_manuals/"):
        try:
            with open(manifest_path, 'r') as f:
                content = f.read().strip()
                self.manifest = json.loads(content) if content else {}
        except (FileNotFoundError, json.JSONDecodeError):
            # Graceful fallback to prevent crashes if file is empty or corrupted
            self.manifest = {}
        self.manuals_dir = manuals_dir

    def inject(self, clean_text: str, metadata: dict) -> str:
        region = metadata.get("region", "US")
        manual_file = self.manifest.get(region, "REG_US_SEC.md")
        full_path = os.path.join(self.manuals_dir, manual_file)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                context = f.read()
        except FileNotFoundError:
            context = "Standard operational compliance verification."

        return f"### REGULATORY COMPLIANCE CONTEXT\n{context}\n\n### SANITIZED TRANSCRIPT DATA\n{clean_text}"
