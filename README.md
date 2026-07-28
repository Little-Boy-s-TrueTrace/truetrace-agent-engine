# TrueTrace Multi-Agent Engine

Asynchronous Python runtime orchestrating three compliance agents:

- Deepfake Inspector handles KYC, CCCD, Alibaba vision/eKYC, and identity registry.
- Money-Trail Explorer analyzes the transaction graph using a sliding window, freezes high-risk accounts, and creates AML alerts.
- AML Reporter uses Qwen to compose bilingual STR drafts for human review.

## Running Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Running Locally

The engine requires Kafka and the TrueTrace backend:

```bash
python main.py
```

Health endpoint: `GET http://localhost:8080/health`.

## AI Mode

Default is `demo`, running offline with deterministic results for demo/test. Do not use demo results as a fraud verdict.

Alibaba Model Studio:

```dotenv
VISION_API_PROVIDER=alibaba-model-studio
VISION_API_KEY=...
VISION_API_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
VISION_MODEL=qwen-vl-plus

LLM_PROVIDER=dashscope
LLM_API_KEY=...
LLM_API_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

Alibaba eKYC gateway:

```dotenv
VISION_API_PROVIDER=alibaba-ekyc
VISION_API_ENDPOINT=https://your-normalizing-gateway.example/deepfake
VISION_API_KEY=...
```

The gateway must return standardized fields: `deepfake_probability`, `face_match_score`, `liveness_score`, `signals`, and `details`.

National CCCD verification is a hypothetical integration and is only invoked when configured:

```dotenv
IDENTITY_REGISTRY_ENDPOINT=https://registry-gateway.example/verify
IDENTITY_REGISTRY_API_KEY=...
```

## Default Rapid Mule Thresholds

- Minimum inflow of 1 billion VND;
- Transfers to at least 20 accounts;
- Within 60 seconds;
- Total outflow at least 80% of inflow;
- Risk score of 7/10 triggers freeze + alert + STR draft.

All thresholds have corresponding environment variables in `truetrace-deployment/.env.example`.
