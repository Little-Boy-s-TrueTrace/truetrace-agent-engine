import base64
import hashlib
import json
import logging
from vision_api import get_provider
from cccd_validator import validate_format
from config import Config
from backend_client import json_text, request
from identity_registry import IdentityRegistryClient

logger = logging.getLogger(__name__)

class DeepfakeInspectorAgent:
    def __init__(self, kafka_producer=None):
        self.kafka_producer = kafka_producer
        self.vision_api = get_provider(Config.VISION_API_PROVIDER)
        self.identity_registry = IdentityRegistryClient()
        
    async def analyze_kyc(self, kyc_session: dict) -> dict:
        logger.info(f"Analyzing KYC session {kyc_session.get('session_id')}")
        
        # 1. Validate Citizen ID
        session_id = kyc_session.get('session_id') or kyc_session.get('sessionId')
        cccd_number = kyc_session.get('cccd_number') or kyc_session.get('cccdNumber', '')
        customer_name = kyc_session.get('customer_name') or kyc_session.get('customerName', '')
        selfie_image = kyc_session.get('face_image_base64') or kyc_session.get('faceImageBase64', '')
        id_front_image = (
            kyc_session.get('id_front_image_base64')
            or kyc_session.get('idFrontImageBase64')
            or kyc_session.get('frontImageBase64', '')
        )
        id_back_image = (
            kyc_session.get('id_back_image_base64')
            or kyc_session.get('idBackImageBase64')
            or kyc_session.get('backImageBase64', '')
        )
        cccd_result = validate_format(cccd_number)
        registry_result = await self.identity_registry.verify(cccd_number, customer_name)
        
        # 2. Vision Analysis
        vision_result = await self.vision_api.analyze_image(
            selfie_image,
            'deepfake',
            kyc_session.get("selfie_filename")
            or kyc_session.get("selfieFilename", ""),
        )
        evidence = {
            "selfie": self._evidence_metadata(selfie_image),
            "id_front": self._evidence_metadata(id_front_image),
            "id_back": self._evidence_metadata(id_back_image),
        }
        
        # 3. Compute Risk Score
        risk_score = 0.0
        if not cccd_result.get('valid'):
            risk_score += 3.0
        if registry_result.get("matched") is False:
            risk_score += 4.0
        if not evidence["id_front"]["present"] or not evidence["id_back"]["present"]:
            risk_score += 3.0
        
        df_prob = vision_result.get('deepfake_probability', 0)
        if df_prob > 0.8:
            risk_score += 7.0
        elif df_prob > 0.5:
            risk_score += 4.0
            
        finding = {
            "session_id": session_id,
            "account_id": kyc_session.get('account_id') or kyc_session.get('accountId'),
            "customer_id": kyc_session.get('customer_id') or kyc_session.get('customerId'),
            "risk_score": min(10.0, risk_score),
            "cccd_validation": cccd_result,
            "identity_registry": registry_result,
            "vision_analysis": vision_result,
            "evidence": evidence,
            "timestamp": kyc_session.get('timestamp') or kyc_session.get('createdAt')
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
                
        try:
            probability = float(vision_result.get("deepfake_probability", 0))
            if probability >= Config.DEEPFAKE_REJECT_THRESHOLD:
                status, action, risk_level = "REJECTED", "BLOCK_ONBOARDING", "CRITICAL"
            elif (
                probability >= Config.DEEPFAKE_REVIEW_THRESHOLD
                or not cccd_result.get("valid")
                or registry_result.get("matched") is False
                or not evidence["id_front"]["present"]
                or not evidence["id_back"]["present"]
            ):
                status, action, risk_level = "MANUAL_REVIEW", "REVIEW_EVIDENCE", "HIGH"
            else:
                status, action, risk_level = "APPROVED", "CONTINUE_ONBOARDING", "LOW"
            await request(
                "PUT",
                f"/api/kyc/sessions/{session_id}/status",
                {
                    "status": status,
                    "agentFindingJson": json_text(finding),
                    "riskLevel": risk_level,
                    "recommendedAction": action,
                    "deepfakeScore": round(probability * 100),
                    "faceMatchScore": round(float(vision_result.get("face_match_score", 0)) * 100),
                    "livenessScore": round(float(vision_result.get("liveness_score", 0)) * 100),
                    "documentIntegrityScore": (
                        100
                        if cccd_result.get("valid")
                        and evidence["id_front"]["present"]
                        and evidence["id_back"]["present"]
                        else 0
                    ),
                    "cccdValid": cccd_result.get("valid"),
                },
            )
        except Exception as e:
            logger.error(f"Failed to call backend API: {e}")
            
        return finding

    @staticmethod
    def _evidence_metadata(value: str) -> dict:
        if not value:
            return {"present": False, "byte_size": 0, "sha256": None}
        encoded = value.split(",", 1)[1] if value.startswith("data:") else value
        raw = base64.b64decode(encoded, validate=True)
        return {
            "present": True,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
