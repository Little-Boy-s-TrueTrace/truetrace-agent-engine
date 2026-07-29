import json
import logging
from typing import Optional
import time
from config import Config
from llm_report_writer import LlmReportWriter
from backend_client import json_text, request

logger = logging.getLogger(__name__)

class AmlReportAgent:
    def __init__(self, kafka_producer=None):
        self.kafka_producer = kafka_producer
        self.llm = LlmReportWriter(Config.LLM_PROVIDER)
        
    async def generate_report(self, alert: dict, kyc_data: Optional[dict] = None) -> dict:
        if kyc_data is None:
            kyc_data = await self._get_compliance_profile(
                alert.get("account") or alert.get("primaryAccountNumber")
            )
        evidence = {
            "alert": alert,
            "kyc_data": kyc_data,
            "timestamp": time.time()
        }
        
        narrative = await self.llm.generate_str_narrative(evidence)
        
        report = {
            "alert_id": alert.get('alert_id'),
            "account": alert.get('account') or alert.get("primaryAccountNumber"),
            "evidence": evidence,
            "subject": kyc_data or {},
            "transaction_details": (
                alert.get("transaction_chain")
                or alert.get("transactionChain")
                or []
            ),
            "narrative_vi": narrative.get('narrative_vi'),
            "narrative_en": narrative.get('narrative_en'),
            "regulatory_references": [
                "Law on Anti-Money Laundering 2022 (No. 14/2022/QH15), Article 26",
                "Circular 09/2023/TT-NHNN, suspicious transaction reporting form",
            ],
            "status": "DRAFT",
            "human_approval_required": True,
            "timestamp": time.time()
        }
        
        if self.kafka_producer:
            try:
                await self.kafka_producer.send_and_wait(
                    Config.TOPIC_REPORTS_STR,
                    json.dumps(report).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Failed to publish STR report to Kafka: {e}")
                
        await self._create_str_report_backend(report)
        return report
        
    async def _create_str_report_backend(self, report: dict):
        try:
            await request(
                "POST",
                "/api/str/reports",
                {
                    "alertId": report["evidence"]["alert"].get("alert_db_id"),
                    "kycSessionId": report["subject"].get("kycSessionDbId"),
                    "reportType": "STR",
                    "status": "DRAFT",
                    "subjectCustomerId": report["subject"].get("customerId"),
                    "subjectFullName": report["subject"].get("fullName"),
                    "subjectCccdNumber": report["subject"].get("cccdNumber"),
                    "narrativeTextVi": report["narrative_vi"],
                    "narrativeTextEn": report["narrative_en"],
                    "evidenceSummaryJson": json_text(report["evidence"]),
                    "transactionDetailsJson": json_text(report["transaction_details"]),
                    "totalAmount": self._total_amount(report["evidence"]["alert"]),
                    "currency": report["evidence"]["alert"].get("currency", "VND"),
                    "riskScore": report["evidence"]["alert"].get("risk_score"),
                    "riskLevel": self._risk_level(
                        report["evidence"]["alert"].get("risk_score")
                    ),
                    "recommendedActionsJson": json_text(
                        ["HUMAN_REVIEW", "PRESERVE_EVIDENCE", "CONSIDER_STR_SUBMISSION"]
                    ),
                    "regulatoryReferencesJson": json_text(
                        report["regulatory_references"]
                    ),
                },
            )
        except Exception as e:
            logger.error(f"Error creating STR report in backend: {e}")

    async def _get_compliance_profile(self, account: Optional[str]) -> dict:
        if not account:
            return {}
        try:
            return await request(
                "GET", f"/api/compliance/accounts/{account}/profile"
            )
        except Exception as exc:
            logger.error("Failed to enrich STR subject for account %s: %s", account, exc)
            return {}

    @staticmethod
    def _total_amount(alert: dict) -> float:
        explicit = alert.get("total_amount") or alert.get("totalAmount")
        if explicit is not None:
            return float(explicit)
        graph = alert.get("graph") or {}
        return max(float(graph.get("total_in", 0)), float(graph.get("total_out", 0)))

    @staticmethod
    def _risk_level(value) -> str:
        score = float(value or 0)
        if score >= 8:
            return "CRITICAL"
        if score >= 5:
            return "HIGH"
        if score >= 3:
            return "MEDIUM"
        return "LOW"
