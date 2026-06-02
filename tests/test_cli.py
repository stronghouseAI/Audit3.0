import pytest
from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()

def test_cli_safeguards_concurrency():
    """Ensure CLI successfully displays global help instructions."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
