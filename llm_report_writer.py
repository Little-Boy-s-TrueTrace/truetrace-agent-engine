import json

import httpx

from config import Config


class LlmReportWriter:
    def __init__(self, provider: str = "demo"):
        self.provider = provider

    async def generate_str_narrative(self, evidence: dict) -> dict:
        if self.provider in {"demo", "mock"}:
            return self._demo_generate(evidence)
        if self.provider in {"dashscope", "alibaba", "qwen"}:
            return await self._dashscope_generate(evidence)
        raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider}")

    @staticmethod
    def _demo_generate(evidence: dict) -> dict:
        alert = evidence.get("alert") or {}
        patterns = ", ".join(
            item.get("pattern", "unknown") for item in alert.get("findings", [])
        ) or "unidentified"
        pattern_labels_vi = {
            "fan_out": "phân tán tiền tới nhiều tài khoản (fan-out)",
            "fan_in": "nhận tiền từ nhiều tài khoản (fan-in)",
            "circular_flow": "dòng tiền vòng tròn",
            "velocity_anomaly": "tần suất giao dịch bất thường",
            "structuring": "chia nhỏ giao dịch để né ngưỡng (structuring)",
            "rapid_mule_dispersion": (
                "nhận và phân tán tiền nhanh qua tài khoản trung gian "
                "(rapid mule dispersion)"
            ),
        }
        patterns_vi = ", ".join(
            pattern_labels_vi.get(
                item.get("pattern", "unknown"),
                item.get("pattern", "không xác định"),
            )
            for item in alert.get("findings", [])
        ) or "chưa xác định"
        account = alert.get("account") or "unidentified"
        score = alert.get("risk_score", 0)
        return {
            "narrative_vi": (
                f"Hệ thống TrueTrace ghi nhận tài khoản {account} có điểm rủi ro "
                f"{score}/10 và dấu hiệu: {patterns_vi}. Dữ liệu giao dịch, thời điểm "
                "phát sinh và quan hệ với các tài khoản đối ứng đã được lưu trong gói "
                "bằng chứng. Cán bộ AML phải xác minh chủ thể, mục đích giao dịch và "
                "phê duyệt quyết định nộp STR."
            ),
            "narrative_en": (
                f"TrueTrace identified account {account} with risk score {score}/10 and "
                f"indicators: {patterns}. Transaction timestamps and counterparty links "
                "are preserved in the evidence package. AML officer review is required."
            ),
        }

    async def _dashscope_generate(self, evidence: dict) -> dict:
        if not Config.LLM_API_KEY:
            raise RuntimeError("dashscope requires LLM_API_KEY")
        payload = {
            "model": Config.LLM_MODEL,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You draft Vietnamese bank Suspicious Transaction Reports. Never invent facts. "
                        "Separate observations from inferences. Return JSON with narrative_vi and "
                        "narrative_en. The draft always requires human approval before submission."
                    ),
                },
                {"role": "user", "content": json.dumps(evidence, ensure_ascii=False, default=str)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {Config.LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{Config.LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=Config.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        if not result.get("narrative_vi") or not result.get("narrative_en"):
            raise ValueError("Qwen response is missing required bilingual narratives")
        return result
