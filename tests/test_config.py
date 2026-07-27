import pytest

from config import Config


def test_demo_runtime_allows_mock_providers(monkeypatch):
    monkeypatch.setattr(Config, "ENVIRONMENT", "demo")
    Config.validate_runtime()


def test_production_runtime_rejects_demo_configuration(monkeypatch):
    monkeypatch.setattr(Config, "ENVIRONMENT", "production")
    monkeypatch.setattr(Config, "VISION_API_PROVIDER", "demo")
    monkeypatch.setattr(Config, "VISION_API_KEY", "")
    monkeypatch.setattr(Config, "IDENTITY_REGISTRY_ENDPOINT", "")
    monkeypatch.setattr(Config, "IDENTITY_REGISTRY_API_KEY", "")
    monkeypatch.setattr(Config, "LLM_PROVIDER", "demo")
    monkeypatch.setattr(Config, "LLM_API_KEY", "")
    monkeypatch.setattr(Config, "INTERNAL_API_TOKEN", "short")
    monkeypatch.setattr(Config, "DB_PASSWORD", "postgres")
    monkeypatch.setattr(Config, "KAFKA_BOOTSTRAP", "localhost:9092")
    monkeypatch.setattr(Config, "REDIS_HOST", "localhost")

    with pytest.raises(RuntimeError, match="Production configuration rejected"):
        Config.validate_runtime()


def test_production_runtime_accepts_real_integrations(monkeypatch):
    monkeypatch.setattr(Config, "ENVIRONMENT", "production")
    monkeypatch.setattr(Config, "VISION_API_PROVIDER", "alibaba-model-studio")
    monkeypatch.setattr(Config, "VISION_API_KEY", "vision-key")
    monkeypatch.setattr(Config, "IDENTITY_REGISTRY_ENDPOINT", "https://identity-registry.internal")
    monkeypatch.setattr(Config, "IDENTITY_REGISTRY_API_KEY", "identity-key")
    monkeypatch.setattr(Config, "LLM_PROVIDER", "dashscope")
    monkeypatch.setattr(Config, "LLM_API_KEY", "llm-key")
    monkeypatch.setattr(Config, "INTERNAL_API_TOKEN", "a" * 32)
    monkeypatch.setattr(Config, "DB_PASSWORD", "strong-secret")
    monkeypatch.setattr(Config, "KAFKA_BOOTSTRAP", "kafka.internal:9093")
    monkeypatch.setattr(Config, "REDIS_HOST", "redis.internal")
    Config.validate_runtime()
