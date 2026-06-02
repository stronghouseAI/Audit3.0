import pytest
from src.upstream.agent_b_injector import DynamicContextInjector

def test_context_injection_stitching(tmp_path):
    # Setup temporary layout simulation
    manifest_file = tmp_path / "test_manifest.json"
    manifest_file.write_text('{"EU": "TEST_EU.md"}')
    
    manuals_dir = tmp_path / "manuals"
    manuals_dir.mkdir()
    (manuals_dir / "TEST_EU.md").write_text("GDPR rules apply.")
    
    injector = DynamicContextInjector(manifest_path=str(manifest_file), manuals_dir=str(manuals_dir))
    
    clean_text = "User requested account data extraction."
    metadata = {"region": "EU"}
    
    output = injector.inject(clean_text, metadata)
    
    assert "GDPR rules apply." in output
    assert "User requested account data extraction." in output
