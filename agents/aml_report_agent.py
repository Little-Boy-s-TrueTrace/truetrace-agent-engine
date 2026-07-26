import json
import logging
from typing import Optional
import time
import aiohttp
from config import Config
from llm_report_writer import LlmReportWriter

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
        url = f"{Config.BACKEND_URL}/api/str/reports"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=report) as resp:
                    logger.info(f"Create STR report response: {resp.status}")
        except Exception as e:
            logger.error(f"Error creating STR report in backend: {e}")
