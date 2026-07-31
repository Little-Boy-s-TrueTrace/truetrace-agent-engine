import pytest
from unittest.mock import AsyncMock
from agents.aml_report_agent import AmlReportAgent

@pytest.mark.asyncio
async def test_aml_report_agent_generates_draft_report(monkeypatch):
    agent = AmlReportAgent()
    agent.llm.generate_str_narrative = AsyncMock(return_value={
        "narrative_vi": "Báo cáo giao dịch đáng ngờ đối với tài khoản ACC-MULE-1.",
        "narrative_en": "Suspicious Transaction Report for account ACC-MULE-1.",
    })
    backend_mock = AsyncMock(return_value={"id": 1, "status": "DRAFT"})
    monkeypatch.setattr("agents.aml_report_agent.request", backend_mock)

    alert = {
        "id": 10,
        "alert_id": "alert-10",
        "alert_db_id": 10,
        "primaryAccountNumber": "ACC-MULE-1",
        "account": "ACC-MULE-1",
        "risk_score": 9.5,
        "totalAmount": 1_000_000_000,
        "currency": "VND",
        "transaction_chain": [
            {"from": "ACC-IN", "to": "ACC-MULE-1", "amount": 1_000_000_000, "tx_id": "tx-1"}
        ]
    }
    kyc_data = {
        "kycSessionDbId": 5,
        "customerId": "cust-5",
        "fullName": "Le Van B",
        "cccdNumber": "001099888777"
    }

    report = await agent.generate_report(alert, kyc_data)

    assert report["status"] == "DRAFT"
    assert report["account"] == "ACC-MULE-1"
    assert report["human_approval_required"] is True
    assert "narrative_vi" in report
    assert "narrative_en" in report
    assert len(report["regulatory_references"]) >= 2
    backend_mock.assert_awaited_once()

@pytest.mark.asyncio
async def test_aml_report_agent_fetches_profile_if_missing_kyc(monkeypatch):
    agent = AmlReportAgent()
    agent.llm.generate_str_narrative = AsyncMock(return_value={
        "narrative_vi": "Mô tả vi phạm.",
        "narrative_en": "Narrative text.",
    })
    profile_mock = AsyncMock(return_value={
        "accountNumber": "ACC-AUTO-LOOKUP",
        "fullName": "Tran Van C",
        "kycSessionDbId": 12
    })
    backend_mock = AsyncMock(return_value={"id": 2, "status": "DRAFT"})
    
    async def mock_request(method, path, *args, **kwargs):
        if "profile" in path:
            return await profile_mock()
        return await backend_mock()

    monkeypatch.setattr("agents.aml_report_agent.request", mock_request)

    alert = {
        "alert_id": "alert-11",
        "primaryAccountNumber": "ACC-AUTO-LOOKUP",
        "risk_score": 8.0,
        "totalAmount": 500_000_000,
    }

    report = await agent.generate_report(alert, kyc_data=None)
    assert report["subject"]["fullName"] == "Tran Van C"
    profile_mock.assert_awaited_once()
