import base64
from unittest.mock import AsyncMock

import pytest

from agents.aml_report_agent import AmlReportAgent
from agents.deepfake_agent import DeepfakeInspectorAgent
from agents.money_trail_agent import MoneyTrailAgent


@pytest.mark.asyncio
async def test_deepfake_agent_produces_reject_recommendation(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.identity_registry.verify = AsyncMock(
        return_value={"status": "VERIFIED", "matched": True, "source": "test"}
    )
    backend = AsyncMock(return_value={})
    monkeypatch.setattr("agents.deepfake_agent.request", backend)
    image = base64.b64encode(b"synthetic deepfake sample").decode()

    finding = await agent.analyze_kyc(
        {
            "session_id": "kyc-1",
            "customer_name": "Nguyen Van A",
            "cccd_number": "001200000001",
            "face_image_base64": image,
            "timestamp": "2026-01-01T00:00:00Z",
        }
    )

    assert finding["vision_analysis"]["deepfake_probability"] > 0.8
    payload = backend.await_args.args[2]
    assert payload["status"] == "REJECTED"
    assert payload["recommendedAction"] == "BLOCK_ONBOARDING"


@pytest.mark.asyncio
async def test_money_trail_agent_freezes_and_escalates_rapid_dispersion():
    agent = MoneyTrailAgent()
    agent._freeze_account = AsyncMock()
    agent._create_alert = AsyncMock()
    now = 1_800_000_000.0

    assert await agent.process_transaction(
        {
            "id": "in-1",
            "sourceAccountNumber": "origin",
            "targetAccountNumber": "mule",
            "amount": 1_000_000_000,
            "timestamp": now,
        }
    ) is None

    result = None
    for index in range(20):
        result = await agent.process_transaction(
            {
                "id": f"out-{index}",
                "sourceAccountNumber": "mule",
                "targetAccountNumber": f"beneficiary-{index}",
                "amount": 45_000_000,
                "timestamp": now + index + 1,
            }
        )

    assert result is not None
    assert result["needs_str"] is True
    assert any(item["pattern"] == "rapid_mule_dispersion" for item in result["findings"])
    agent._freeze_account.assert_awaited_with("mule")
    agent._create_alert.assert_awaited()


@pytest.mark.asyncio
async def test_aml_report_is_draft_and_requires_human_approval(monkeypatch):
    agent = AmlReportAgent()
    backend = AsyncMock(return_value={})
    monkeypatch.setattr("agents.aml_report_agent.request", backend)

    report = await agent.generate_report(
        {
            "alert_id": "alert-1",
            "account": "mule",
            "risk_score": 10,
            "findings": [{"pattern": "rapid_mule_dispersion"}],
        }
    )

    assert report["status"] == "DRAFT"
    assert report["human_approval_required"] is True
    assert "mule" in report["narrative_vi"]
