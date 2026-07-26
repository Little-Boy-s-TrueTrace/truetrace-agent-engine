import json
import logging
from vision_api import get_provider
from cccd_validator import validate_format
from config import Config

logger = logging.getLogger(__name__)

class DeepfakeInspectorAgent:
    def __init__(self, kafka_producer=None):
        self.kafka_producer = kafka_producer
        self.vision_api = get_provider(Config.VISION_API_PROVIDER)
        
    async def analyze_kyc(self, kyc_session: dict) -> dict:
        logger.info(f"Analyzing KYC session {kyc_session.get('session_id')}")
        
        # 1. Validate CCCD
        cccd_result = validate_format(kyc_session.get('cccd_number', ''))
        
        # 2. Vision Analysis
        vision_result = await self.vision_api.analyze_image(
            kyc_session.get('face_image_base64', ''),
            'deepfake'
        )
        
        # 3. Compute Risk Score
        risk_score = 0.0
        if not cccd_result.get('valid'):
            risk_score += 3.0
        
        df_prob = vision_result.get('deepfake_probability', 0)
        if df_prob > 0.8:
            risk_score += 7.0
        elif df_prob > 0.5:
            risk_score += 4.0
            
        finding = {
            "session_id": kyc_session.get('session_id'),
            "account_id": kyc_session.get('account_id'),
            "risk_score": risk_score,
            "cccd_validation": cccd_result,
            "vision_analysis": vision_result,
            "timestamp": kyc_session.get('timestamp')
        }
        
        # Publish finding to Kafka
        if self.kafka_producer:
            try:
                await self.kafka_producer.send_and_wait(
                    Config.TOPIC_FINDINGS_DEEPFAKE,
                    json.dumps(finding).encode('utf-8')
                )
            except Exception as e:
                logger.error(f"Failed to publish to Kafka: {e}")
                
        import httpx
        try:
            url = f"{Config.BACKEND_URL}/api/kyc/sessions/{kyc_session.get('session_id')}/status"
            async with httpx.AsyncClient() as client:
                await client.put(url, json={"finding": finding})
        except Exception as e:
            logger.error(f"Failed to call backend API: {e}")
            
        return finding
