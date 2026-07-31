import base64
import pytest
from unittest.mock import AsyncMock
from agents.deepfake_agent import DeepfakeInspectorAgent

SAMPLE_B64 = base64.b64encode(b"dummy_image_data_for_test").decode("utf-8")

@pytest.mark.asyncio
async def test_deepfake_agent_approves_valid_kyc(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.vision_api.analyze_image = AsyncMock(return_value={
        "face_matched": True,
        "liveness_verified": True,
        "deepfake_probability": 0.05,
        "details": "Valid live human selfie"
    })
    agent.identity_registry.verify = AsyncMock(return_value={
        "matched": True,
        "fullName": "Nguyen Van A",
        "status": "VALID"
    })
    backend_mock = AsyncMock(return_value={"status": "APPROVED"})
    monkeypatch.setattr("agents.deepfake_agent.request", backend_mock)

    session = {
        "session_id": "session-100",
        "account_id": "ACC-100",
        "cccd_number": "001099123456",
        "customer_name": "Nguyen Van A",
        "face_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_front_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_back_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
    }

    result = await agent.analyze_kyc(session)
    assert result["risk_score"] < 4.0
    assert result["cccd_validation"]["valid"] is True
    assert result["identity_registry"]["matched"] is True
    assert result["vision_analysis"]["deepfake_probability"] == 0.05
    backend_mock.assert_awaited_once()

@pytest.mark.asyncio
async def test_deepfake_agent_rejects_synthetic_deepfake(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.vision_api.analyze_image = AsyncMock(return_value={
        "face_matched": False,
        "liveness_verified": False,
        "deepfake_probability": 0.95,
        "details": "Synthetic deepfake artifact detected"
    })
    agent.identity_registry.verify = AsyncMock(return_value={
        "matched": True,
        "fullName": "Nguyen Van A",
        "status": "VALID"
    })
    backend_mock = AsyncMock(return_value={"status": "REJECTED"})
    monkeypatch.setattr("agents.deepfake_agent.request", backend_mock)

    session = {
        "session_id": "session-101",
        "account_id": "ACC-101",
        "cccd_number": "001099123456",
        "customer_name": "Nguyen Van A",
        "face_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_front_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_back_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
    }

    result = await agent.analyze_kyc(session)
    assert result["risk_score"] >= 7.0
    assert result["vision_analysis"]["deepfake_probability"] == 0.95
    backend_mock.assert_awaited_once()

@pytest.mark.asyncio
async def test_deepfake_agent_escalates_invalid_cccd(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.vision_api.analyze_image = AsyncMock(return_value={
        "face_matched": True,
        "liveness_verified": True,
        "deepfake_probability": 0.1,
    })
    agent.identity_registry.verify = AsyncMock(return_value={
        "matched": False,
        "status": "NOT_FOUND"
    })
    backend_mock = AsyncMock(return_value={"status": "MANUAL_REVIEW"})
    monkeypatch.setattr("agents.deepfake_agent.request", backend_mock)

    session = {
        "session_id": "session-102",
        "account_id": "ACC-102",
        "cccd_number": "invalid_cccd",
        "customer_name": "Nguyen Van A",
        "face_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_front_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_back_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
    }

    result = await agent.analyze_kyc(session)
    assert result["cccd_validation"]["valid"] is False
    assert result["identity_registry"]["matched"] is False
    backend_mock.assert_awaited_once()
