import httpx

from config import Config


class IdentityRegistryClient:
    """Adapter for the assumed national identity registry API.

    Demo mode validates the Citizen ID format only. Production deployments must configure
    IDENTITY_REGISTRY_ENDPOINT and IDENTITY_REGISTRY_API_KEY.
    """

    def __init__(self) -> None:
        import os

        self.endpoint = os.getenv("IDENTITY_REGISTRY_ENDPOINT", "")
        self.api_key = os.getenv("IDENTITY_REGISTRY_API_KEY", "")

    async def verify(self, cccd_number: str, customer_name: str) -> dict:
        if not self.endpoint:
            return {
                "status": "NOT_CONFIGURED",
                "matched": None,
                "source": "demo-format-check",
            }
        if not self.api_key:
            raise RuntimeError("IDENTITY_REGISTRY_API_KEY is required when endpoint is configured")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"cccdNumber": cccd_number, "fullName": customer_name}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        return {
            "status": "VERIFIED",
            "matched": bool(data.get("matched")),
            "source": data.get("source", "national-identity-registry"),
            "reference_id": data.get("referenceId"),
        }
