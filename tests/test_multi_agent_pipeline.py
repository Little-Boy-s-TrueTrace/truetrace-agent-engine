import base64
import pytest
from unittest.mock import AsyncMock
from agents.deepfake_agent import DeepfakeInspectorAgent
from agents.money_trail_agent import MoneyTrailAgent
from agents.aml_report_agent import AmlReportAgent

SAMPLE_B64 = base64.b64encode(b"dummy_image_data_for_test").decode("utf-8")

@pytest.mark.asyncio
async def test_full_multi_agent_pipeline_e2e_flow(monkeypatch):
    """
    Integration unit test tracking end-to-end flow through all 3 autonomous agents:
    1. Agent 1 (Deepfake Inspector): Processes eKYC & auto-approves legitimate user.
    2. Agent 2 (Money-Trail Explorer): Detects rapid dispersion anomaly & triggers AUTO-FREEZE.
    3. Agent 3 (AML STR Reporter): Generates bilingual STR draft for human compliance review.
    """
    # ----------------------------------------------------
    # Step 1: Agent 1 - Identity Onboarding & Deepfake Check
    # ----------------------------------------------------
    agent1 = DeepfakeInspectorAgent()
    agent1.vision_api.analyze_image = AsyncMock(return_value={
        "face_matched": True,
        "liveness_verified": True,
        "deepfake_probability": 0.02,
    })
    agent1.identity_registry.verify = AsyncMock(return_value={
        "matched": True,
        "fullName": "Mule Candidate A",
        "status": "VALID"
    })
    backend_kyc_mock = AsyncMock(return_value={"status": "APPROVED"})
    monkeypatch.setattr("agents.deepfake_agent.request", backend_kyc_mock)

    kyc_session = {
        "session_id": "pipeline-kyc-01",
        "account_id": "ACC-PIPELINE-MULE",
        "cccd_number": "001099000111",
        "customer_name": "Mule Candidate A",
        "face_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_front_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
        "id_back_image_base64": f"data:image/png;base64,{SAMPLE_B64}",
    }
    kyc_result = await agent1.analyze_kyc(kyc_session)
    assert kyc_result["risk_score"] < 4.0
    assert kyc_result["cccd_validation"]["valid"] is True

    # ----------------------------------------------------
    # Step 2: Agent 2 - Real-time Fraud & Money Trail Containment
    # ----------------------------------------------------
    agent2 = MoneyTrailAgent()
    agent2._freeze_account = AsyncMock()
    agent2._create_alert = AsyncMock()
    now = 1_900_000_000.0

    # Inflow transaction
    await agent2.process_transaction({
        "id": "pipe-tx-in-1",
        "sourceAccountNumber": "ACC-FUNDER",
        "targetAccountNumber": "ACC-PIPELINE-MULE",
        "amount": 1_000_000_000,
        "timestamp": now,
    })

    # Outflow transaction 1
    t1 = await agent2.process_transaction({
        "id": "pipe-tx-out-1",
        "sourceAccountNumber": "ACC-PIPELINE-MULE",
        "targetAccountNumber": "ACC-REC-1",
        "amount": 180_000_000,
        "timestamp": now + 2,
    })
    assert t1["needs_str"] is False

    # Outflow transaction 2 (rapid transfer continuous burst -> triggers freeze)
    t2 = await agent2.process_transaction({
        "id": "pipe-tx-out-2",
        "sourceAccountNumber": "ACC-PIPELINE-MULE",
        "targetAccountNumber": "ACC-REC-2",
        "amount": 150_000_000,
        "timestamp": now + 5,
    })

    assert t2["needs_str"] is True
    assert t2["risk_score"] >= 7.0
    agent2._freeze_account.assert_awaited_once_with("ACC-PIPELINE-MULE")

    # ----------------------------------------------------
    # Step 3: Agent 3 - Autonomous STR Narrative Generation
    # ----------------------------------------------------
    agent3 = AmlReportAgent()
    agent3.llm.generate_str_narrative = AsyncMock(return_value={
        "narrative_vi": "Phát hiện hành vi rửa tiền dòng tiền nhanh qua tài khoản ACC-PIPELINE-MULE.",
        "narrative_en": "Detected rapid dispersion money laundering flow on account ACC-PIPELINE-MULE.",
    })
    backend_report_mock = AsyncMock(return_value={"id": 100, "status": "DRAFT"})
    monkeypatch.setattr("agents.aml_report_agent.request", backend_report_mock)

    alert_payload = {
        "id": 50,
        "alert_id": "alert-pipeline-50",
        "alert_db_id": 50,
        "primaryAccountNumber": t2["account"],
        "risk_score": t2["risk_score"],
        "totalAmount": t2["total_amount"],
        "currency": "VND",
        "transaction_chain": t2["transaction_chain"],
    }
    subject_kyc = {
        "kycSessionDbId": 99,
        "customerId": "cust-mule-01",
        "fullName": "Mule Candidate A",
        "cccdNumber": "001099000111",
    }

    report = await agent3.generate_report(alert_payload, kyc_data=subject_kyc)
    assert report["status"] == "DRAFT"
    assert report["account"] == "ACC-PIPELINE-MULE"
    assert report["human_approval_required"] is True
    assert report["narrative_vi"] != ""
    assert report["narrative_en"] != ""
