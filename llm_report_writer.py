class LlmReportWriter:
    def __init__(self, provider: str = 'mock'):
        self.provider = provider
        
    async def generate_str_narrative(self, evidence: dict) -> dict:
        if self.provider == 'mock':
            return self._mock_generate(evidence)
        elif self.provider == 'bedrock':
            return self._bedrock_generate(evidence)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
            
    def _mock_generate(self, evidence: dict) -> dict:
        return {
            "narrative_vi": "Báo cáo Giao dịch Đáng ngờ (STR). Khách hàng có dấu hiệu sử dụng tài khoản ảo (Deepfake). Các giao dịch liên tục và chia nhỏ để lách luật.",
            "narrative_en": "Suspicious Transaction Report (STR). The customer shows signs of using a virtual account (Deepfake). Transactions are continuous and structured to bypass regulations."
        }
        
    def _bedrock_generate(self, evidence: dict) -> dict:
        # Placeholder for AWS Bedrock with Qwen
        return {
            "narrative_vi": "Báo cáo STR từ Bedrock (chưa triển khai).",
            "narrative_en": "STR report from Bedrock (not yet implemented)."
        }
