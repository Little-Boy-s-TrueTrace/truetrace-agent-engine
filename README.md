# TrueTrace Agent Engine

[![Git Clones](https://badgen.net/https/cdn.jsdelivr.net/gh/Little-Boy-s-TrueTrace/truetrace-deployment@main/truetrace-engine-clone-badge.json)](https://github.com/Little-Boy-s-TrueTrace/truetrace-deployment)
[![Unique Cloners](https://badgen.net/https/cdn.jsdelivr.net/gh/Little-Boy-s-TrueTrace/truetrace-deployment@main/truetrace-engine-uniques-badge.json)](https://github.com/Little-Boy-s-TrueTrace/truetrace-deployment)
[![Release Downloads](https://badgen.net/https/cdn.jsdelivr.net/gh/Little-Boy-s-TrueTrace/truetrace-deployment@main/downloads-badge.json)](https://github.com/Little-Boy-s-TrueTrace/truetrace-deployment/releases)

> **Part of the [Little Boy's TrueTrace](https://github.com/Little-Boy-s-TrueTrace) project** -- an end-to-end AI-powered banking security platform.

The **TrueTrace Agent Engine (Multi-Agent Deepfake & AML Compliance Orchestrator)** serves as the central brain of the defensive ecosystem. It ingests fraud alerts, deepfake analysis findings, correlates cross-channel data, verifies transactions, and performs automated compliance tracking and account protection under strict policy guardrails.

---

## Key Features & Architecture

### 1. Multi-Stream Ingestion & Correlation
The engine runs a Kafka consumer pipeline listening to fraud telemetry and transaction alerts. To avoid duplicate alerts and analyze complex fraud schemes, incoming findings enter an in-memory sliding correlation window. Alerts are grouped by primary entity: IP Addresses, Usernames, or Account IDs.

### 2. Independent Transaction Verification
Before acting on a finding, the engine crosschecks the alert by querying clean PostgreSQL database access logs. This determines if the suspicious pattern reported actually occurred on the backend, setting a verification strength indicator.

### 3. AI-Powered Compliance Orchestrator
The engine utilizes a custom AI Agent (powered by Qwen 3 Plus or OpenAI-compatible LLMs) to analyze the correlated findings and log evidence. It calculates risk scores, verifies compliance policies, and executes risk mitigation protocols.

### 4. Redis State Tracking
All incidents maintain live state in a Redis database. State transitions are recorded with timestamps, action completion rates, and transaction rollbacks.

### 5. Auto-Containment Policy Gates
Actions (like account blocks, transaction holds) are only executed if all the following gates pass:
* **Autopilot Mode**: The autopilot setting is explicitly enabled.
* **Verification**: Log verification state is confirmed.
* **OPA Authorization**: Open Policy Agent authorization returns `allow`.

---

## Getting Started

### Prerequisites
* **Python 3.11+**
* **Apache Kafka & Redis**
* **PostgreSQL Database**

### Running the Engine (Host Mode)
1. Install Python requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the engine:
   ```bash
   python main.py
   ```

### Standalone Container Mode
```bash
docker build -t truetrace-agent-engine .
docker run -d \
  -e KAFKA_BROKERS=host.docker.internal:9094 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e DATABASE_URL=postgresql://postgres:1@host.docker.internal:5432/truetrace \
  -e LLM_PROVIDER=bedrock \
  --name truetrace-agent-engine-service \
  truetrace-agent-engine
```

---

## Testing

Run tests using `pytest` inside the engine directory:

```bash
pytest
```
