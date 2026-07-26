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
        evidence = {
            "alert": alert,
            "kyc_data": kyc_data,
            "timestamp": time.time()
        }
        
        narrative = await self.llm.generate_str_narrative(evidence)
        
        report = {
            "alert_id": alert.get('alert_id'),
            "account": alert.get('account'),
            "evidence": evidence,
            "narrative_vi": narrative.get('narrative_vi'),
            "narrative_en": narrative.get('narrative_en'),
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
                    "reportType": "STR",
                    "status": "DRAFT",
                    "narrativeTextVi": report["narrative_vi"],
                    "narrativeTextEn": report["narrative_en"],
                    "evidenceSummaryJson": json_text(report["evidence"]),
                    "riskScore": report["evidence"]["alert"].get("risk_score"),
                    "riskLevel": "HIGH",
                    "recommendedActionsJson": json_text(
                        ["HUMAN_REVIEW", "PRESERVE_EVIDENCE", "CONSIDER_STR_SUBMISSION"]
                    ),
                },
            )
        except Exception as e:
            logger.error(f"Error creating STR report in backend: {e}")
