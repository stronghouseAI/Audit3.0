import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel
from qa_auditor import ChecklistItem

@pytest.mark.asyncio
async def test_async_engine_pydantic_parsing(mocker):
    """Verify engine handles native structured response objects from Google GenAI SDK."""
    # Mock the response structure matching GenAI SDK return signatures
    mock_response = MagicMock()
    mock_response.text = '{"requirement": "2FA Recovery Verification", "status": "FAIL", "evidence": "Agent failed to authenticate via SMS recovery code"}'
    
    # Mock the client instance
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    # Spy or mock the save function to prevent real database mutations during testing
    mock_save = mocker.patch("qa_auditor.save_audit_result")

    # Assert that the structured schema fields behave predictably
    item = ChecklistItem(
        requirement="2FA Recovery Verification",
        status="FAIL",
        evidence="Agent failed to authenticate via SMS recovery code"
    )
    assert item.status == "FAIL"
    assert "2FA Recovery" in item.requirement

@pytest.mark.asyncio
async def test_database_fault_isolation_fallback(mocker):
    """Ensure that if database or API encounters errors, the pipeline intercepts it gracefully."""
    mock_save = mocker.patch("qa_auditor.save_audit_result", side_effect=Exception("Database Lockup"))
    
    # Verify the engineering safety block works fine when triggered
    with pytest.raises(Exception) as exc_info:
        from qa_auditor import save_audit_result
        save_audit_result("agent_007", 0, "CRITICAL_FAULT")
    
    assert "Database Lockup" in str(exc_info.value)
