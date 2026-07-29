import base64
import json
from typing import Any

import httpx

from config import Config


class VisionApiClient:
    """Alibaba vision adapter with an explicit, deterministic offline demo mode."""

    def __init__(self, provider: str = "demo"):
        self.provider = provider

    async def analyze_image(
        self,
        image_base64: str,
        analysis_type: str = "deepfake",
        source_filename: str = "",
    ) -> dict:
        raw = self._validate_image(image_base64)
        if self.provider in {"demo", "mock"}:
            return self._demo_analyze(raw, source_filename)
        if self.provider in {"alibaba", "alibaba-model-studio"}:
            return await self._model_studio_analyze(image_base64)
        if self.provider == "alibaba-ekyc":
            return await self._ekyc_analyze(raw)
        raise ValueError(f"Unsupported VISION_API_PROVIDER: {self.provider}")

    @staticmethod
    def _validate_image(value: str) -> bytes:
        if not value:
            raise ValueError("face_image_base64 is required")
        encoded = value.split(",", 1)[1] if value.startswith("data:") else value
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("face_image_base64 is not valid base64") from exc
        if not raw:
            raise ValueError("face image is empty")
        if len(raw) > Config.MAX_IMAGE_BYTES:
            raise ValueError("face image exceeds configured size limit")
        return raw

    @staticmethod
    def _demo_analyze(raw: bytes, source_filename: str = "") -> dict:
        marker = raw.lower()
        filename_marker = source_filename.lower()
        suspicious = (
            b"deepfake" in marker
            or b"synthetic" in marker
            or "deepfake" in filename_marker
            or "synthetic" in filename_marker
        )
        return {
            "provider": "demo",
            "deepfake_probability": 0.91 if suspicious else 0.08,
            "face_match_score": 0.52 if suspicious else 0.96,
            "liveness_score": 0.31 if suspicious else 0.94,
            "signals": ["demo_synthetic_marker"] if suspicious else [],
            "model_explanation": "Deterministic offline demonstration; not a production verdict.",
        }

    async def _model_studio_analyze(self, image_base64: str) -> dict:
        self._require_credentials()
        data_url = image_base64 if image_base64.startswith("data:") else f"data:image/jpeg;base64,{image_base64}"
        payload = {
            "model": Config.VISION_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a bank eKYC forensic triage model. Inspect visual artifacts, "
                        "face consistency and presentation-attack indicators. Return JSON only "
                        "with deepfake_probability, face_match_score, liveness_score (0..1), "
                        "signals (array), and model_explanation. This is decision support, not proof."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "Assess this eKYC selfie for synthetic or replay indicators."},
                    ],
                },
            ],
            "temperature": 0,
        }
        result = await self._post_json(
            f"{Config.VISION_API_ENDPOINT.rstrip('/')}/chat/completions", payload
        )
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return self._normalize(parsed, "alibaba-model-studio")

    async def _ekyc_analyze(self, raw: bytes) -> dict:
        """Call a configured Alibaba eKYC gateway that returns normalized risk fields."""
        self._require_credentials()
        headers = {"Authorization": f"Bearer {Config.VISION_API_KEY}"}
        async with httpx.AsyncClient(timeout=Config.VISION_TIMEOUT_SECONDS) as client:
            response = await client.post(
                Config.VISION_API_ENDPOINT,
                headers=headers,
                files={"file": ("selfie.jpg", raw, "image/jpeg")},
            )
            response.raise_for_status()
        return self._normalize(response.json(), "alibaba-ekyc")

    async def _post_json(self, url: str, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {Config.VISION_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=Config.VISION_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _normalize(value: dict[str, Any], provider: str) -> dict:
        def score(*keys: str, default: float = 0.0) -> float:
            current: Any = value
            for key in keys:
                current = current.get(key) if isinstance(current, dict) else None
            try:
                return max(0.0, min(1.0, float(current)))
            except (TypeError, ValueError):
                return default

        return {
            "provider": provider,
            "deepfake_probability": score("deepfake_probability", default=score("confidence")),
            "face_match_score": score("face_match_score"),
            "liveness_score": score("liveness_score"),
            "signals": value.get("signals") or value.get("riskTags") or [],
            "model_explanation": value.get("model_explanation") or value.get("details") or "",
        }

    def _require_credentials(self) -> None:
        if not Config.VISION_API_KEY or not Config.VISION_API_ENDPOINT:
            raise RuntimeError(f"{self.provider} requires VISION_API_KEY and VISION_API_ENDPOINT")

def get_provider(provider_name: str) -> VisionApiClient:
    return VisionApiClient(provider=provider_name)
