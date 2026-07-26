import json
from typing import Any

import httpx

from config import Config


def internal_headers() -> dict[str, str]:
    return (
        {"X-TrueTrace-Internal-Token": Config.INTERNAL_API_TOKEN}
        if Config.INTERNAL_API_TOKEN
        else {}
    )


async def request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
    url = f"{Config.BACKEND_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.request(
            method,
            url,
            headers=internal_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json() if response.content else {}


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
