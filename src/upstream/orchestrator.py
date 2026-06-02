try:
    # Standard absolute import used during root-level testing/pytest execution
    from src.upstream.agent_a_scrubber import LocalPIIScrubber
    from src.upstream.agent_b_injector import DynamicContextInjector
except ModuleNotFoundError:
    # Fallback import used when the CLI tool is executed globally via entrypoints
    from upstream.agent_a_scrubber import LocalPIIScrubber
    from upstream.agent_b_injector import DynamicContextInjector

class UpstreamOrchestrator:
    def __init__(self):
        self.scrubber = LocalPIIScrubber()
        self.injector = DynamicContextInjector()

    def process_pipeline(self, raw_transcript: str, metadata: dict) -> str:
        clean_text = self.scrubber.scrub(raw_transcript)
        final_payload = self.injector.inject(clean_text, metadata)
        return final_payload
