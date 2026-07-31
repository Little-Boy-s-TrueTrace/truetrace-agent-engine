import base64
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from agents.aml_report_agent import AmlReportAgent
from agents.deepfake_agent import DeepfakeInspectorAgent
from agents.money_trail_agent import MoneyTrailAgent
from llm_report_writer import LlmReportWriter


def test_money_trail_accepts_jackson_local_datetime_array():
    value = [2026, 7, 26, 14, 59, 14, 30256906]

    timestamp = MoneyTrailAgent._timestamp(value)

    assert datetime.fromtimestamp(timestamp) == datetime(
        2026, 7, 26, 14, 59, 14, 30256
    )


def test_demo_str_writer_returns_distinct_vietnamese_and_english_narratives():
    report = LlmReportWriter._demo_generate(
        {
            "alert": {
                "account": "ACC-424242",
                "risk_score": 8,
                "findings": [{"pattern": "structuring"}],
            }
        }
    )

    assert "Hệ thống TrueTrace ghi nhận tài khoản ACC-424242" in report["narrative_vi"]
    assert "chia nhỏ giao dịch để né ngưỡng" in report["narrative_vi"]
    assert "TrueTrace identified account ACC-424242" in report["narrative_en"]
    assert report["narrative_vi"] != report["narrative_en"]


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
async def test_deepfake_demo_rejects_synthetic_filename_marker(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.identity_registry.verify = AsyncMock(
        return_value={"status": "VERIFIED", "matched": True, "source": "test"}
    )
    backend = AsyncMock(return_value={})
    monkeypatch.setattr("agents.deepfake_agent.request", backend)

    finding = await agent.analyze_kyc(
        {
            "session_id": "kyc-filename-marker",
            "customer_name": "Nguyen Van A",
            "cccd_number": "001200000001",
            "selfie_filename": "synthetic_deepfake_test.png",
            "face_image_base64": base64.b64encode(b"ordinary png bytes").decode(),
            "id_front_image_base64": base64.b64encode(b"front").decode(),
            "id_back_image_base64": base64.b64encode(b"back").decode(),
        }
    )

    assert finding["vision_analysis"]["deepfake_probability"] == 0.91
    assert backend.await_args.args[2]["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_deepfake_agent_approves_clean_complete_evidence(monkeypatch):
    agent = DeepfakeInspectorAgent()
    agent.identity_registry.verify = AsyncMock(
        return_value={"status": "VERIFIED", "matched": True, "source": "test"}
    )
    backend = AsyncMock(return_value={})
    monkeypatch.setattr("agents.deepfake_agent.request", backend)
    selfie = base64.b64encode(b"clean selfie image").decode()
    front = base64.b64encode(b"cccd front image").decode()
    back = base64.b64encode(b"cccd back image").decode()

    finding = await agent.analyze_kyc(
        {
            "session_id": "kyc-clean",
            "customer_id": "42",
            "account_id": "ACC-424242",
            "customer_name": "Nguyen Van A",
            "cccd_number": "001200000001",
            "face_image_base64": selfie,
            "id_front_image_base64": front,
            "id_back_image_base64": back,
            "timestamp": "2026-01-01T00:00:00Z",
        }
    )

    payload = backend.await_args.args[2]
    assert payload["status"] == "APPROVED"
    assert payload["documentIntegrityScore"] == 100
    assert finding["customer_id"] == "42"
    assert finding["account_id"] == "ACC-424242"
    assert finding["evidence"]["selfie"]["byte_size"] == len(b"clean selfie image")
    assert finding["evidence"]["id_front"]["sha256"]
    assert finding["evidence"]["id_back"]["sha256"]


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
    assert result["total_amount"] == 1_000_000_000
    assert any(item["pattern"] == "rapid_mule_dispersion" for item in result["findings"])
    roles = {
        item["accountNumber"]: item["role"]
        for item in result["involved_accounts"]
    }
    node_types = {
        item["id"]: item["type"]
        for item in result["graph_data"]["nodes"]
    }
    assert roles["origin"] == "SOURCE"
    assert roles["mule"] == "INTERMEDIARY"
    assert roles["beneficiary-19"] == "DESTINATION"
    assert node_types["origin"] == "source"
    assert node_types["mule"] == "intermediary"
    assert node_types["beneficiary-19"] == "destination"
    agent._freeze_account.assert_awaited_with("mule")
    agent._create_alert.assert_awaited()


@pytest.mark.asyncio
async def test_money_trail_repeated_structuring_escalates_on_second_transfer():
    agent = MoneyTrailAgent()
    agent._freeze_account = AsyncMock()
    agent._create_alert = AsyncMock()
    now = 1_800_000_000.0

    first = await agent.process_transaction(
        {
            "id": "structured-1",
            "sourceAccountNumber": "ACC-SOURCE",
            "targetAccountNumber": "ACC-TARGET",
            "amount": 190_000_000,
            "timestamp": now,
        }
    )
    assert first["needs_str"] is False
    assert first["alert_type"] == "STRUCTURING"
    assert first["risk_score"] < 7
    agent._freeze_account.assert_not_awaited()
    agent._create_alert.assert_not_awaited()

    second = await agent.process_transaction(
        {
            "id": "structured-2",
            "sourceAccountNumber": "ACC-SOURCE",
            "targetAccountNumber": "ACC-TARGET",
            "amount": 190_000_000,
            "timestamp": now + 10,
        }
    )

    assert second["needs_str"] is True
    assert second["risk_score"] >= 7
    assert second["alert_type"] == "STRUCTURING"
    assert second["total_amount"] == 380_000_000
    assert len(second["transaction_chain"]) == 2
    roles = {
        item["accountNumber"]: item["role"]
        for item in second["involved_accounts"]
    }
    assert roles["ACC-SOURCE"] == "SOURCE"
    assert roles["ACC-TARGET"] == "DESTINATION"
    agent._freeze_account.assert_awaited_once_with("ACC-SOURCE")
    agent._create_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_money_trail_freezes_on_rapid_continuous_transfers_with_different_amounts():
    agent = MoneyTrailAgent()
    agent._freeze_account = AsyncMock()
    agent._create_alert = AsyncMock()
    now = 1_800_000_000.0

    # 1st transfer: 100k
    t1 = await agent.process_transaction({
        "id": "diff-1",
        "sourceAccountNumber": "ACC-MULE-DIFF",
        "targetAccountNumber": "ACC-REC-1",
        "amount": 100_000,
        "timestamp": now,
    })
    assert t1["needs_str"] is False

    # 2nd transfer: 500k (within 10s)
    t2 = await agent.process_transaction({
        "id": "diff-2",
        "sourceAccountNumber": "ACC-MULE-DIFF",
        "targetAccountNumber": "ACC-REC-2",
        "amount": 500_000,
        "timestamp": now + 5,
    })
    assert t2["needs_str"] is True
    assert t2["risk_score"] >= 7.0
    agent._freeze_account.assert_awaited_once_with("ACC-MULE-DIFF")


@pytest.mark.asyncio
async def test_money_trail_alert_uses_full_suspicious_amount(monkeypatch):
    agent = MoneyTrailAgent()
    backend = AsyncMock(return_value={"id": 9, "alertId": "alert-9"})
    monkeypatch.setattr("agents.money_trail_agent.request", backend)
    agent.graph.add_transaction("in-1", "origin", "mule", 1_000_000_000, 100)
    agent.graph.add_transaction("out-1", "mule", "target", 800_000_000, 101)
    finding = {
        "tx_id": "out-1",
        "account": "mule",
        "risk_score": 10,
        "graph": agent.graph.get_account_stats("mule"),
        "findings": [
            {
                "pattern": "rapid_mule_dispersion",
                "details": {"total_in": 1_000_000_000, "total_out": 800_000_000},
            }
        ],
    }

    await agent._create_alert(finding, 40_000_000)

    payload = backend.await_args.args[2]
    assert payload["totalAmount"] == 1_000_000_000
    assert finding["alert_id"] == "alert-9"
    assert finding["alert_db_id"] == 9


@pytest.mark.asyncio
async def test_aml_report_is_draft_and_requires_human_approval(monkeypatch):
    agent = AmlReportAgent()
    backend = AsyncMock(return_value={})
    monkeypatch.setattr("agents.aml_report_agent.request", backend)

    report = await agent.generate_report(
        {
            "alert_id": "alert-1",
            "alert_db_id": 1,
            "account": "mule",
            "risk_score": 10,
            "graph": {"total_in": 1_000_000_000, "total_out": 800_000_000},
            "findings": [{"pattern": "rapid_mule_dispersion"}],
        }
    )

    assert report["status"] == "DRAFT"
    assert report["human_approval_required"] is True
    assert "mule" in report["narrative_vi"]
    payload = backend.await_args.args[2]
    assert payload["alertId"] == 1
    assert payload["totalAmount"] == 1_000_000_000


@pytest.mark.asyncio
async def test_aml_report_enriches_subject_transactions_and_regulatory_refs(monkeypatch):
    agent = AmlReportAgent()

    async def backend_request(method, path, payload=None):
        if method == "GET":
            assert path == "/api/compliance/accounts/ACC-424242/profile"
            return {
                "customerId": "42",
                "fullName": "Nguyen Van A",
                "cccdNumber": "001200000001",
                "kycSessionDbId": 7,
            }
        assert method == "POST"
        return {"id": 11, **(payload or {})}

    backend = AsyncMock(side_effect=backend_request)
    monkeypatch.setattr("agents.aml_report_agent.request", backend)
    transaction_chain = [
        {
            "txId": "structured-2",
            "from": "ACC-424242",
            "to": "ACC-111111",
            "amount": 190_000_000,
            "timestamp": "2026-01-01T00:00:10Z",
            "channel": "bank_transfer",
        }
    ]

    report = await agent.generate_report(
        {
            "alert_id": "alert-11",
            "alert_db_id": 11,
            "account": "ACC-424242",
            "risk_score": 8,
            "total_amount": 370_000_000,
            "currency": "VND",
            "transaction_chain": transaction_chain,
            "findings": [{"pattern": "structuring"}],
        }
    )

    post_payload = backend.await_args_list[-1].args[2]
    assert report["status"] == "DRAFT"
    assert post_payload["subjectCustomerId"] == "42"
    assert post_payload["subjectFullName"] == "Nguyen Van A"
    assert post_payload["subjectCccdNumber"] == "001200000001"
    assert post_payload["kycSessionId"] == 7
    assert "structured-2" in post_payload["transactionDetailsJson"]
    assert "09/2023/TT-NHNN" in post_payload["regulatoryReferencesJson"]
