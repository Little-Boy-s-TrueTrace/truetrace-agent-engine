FROM python:3.11-slim

LABEL name="truetrace-agent-engine"

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code files
COPY *.py .
COPY agents/ ./agents/

ENTRYPOINT ["python", "main.py"]
