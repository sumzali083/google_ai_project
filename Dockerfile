FROM python:3.11-slim

WORKDIR /app

# Install Node.js + npm, then pre-install mongodb-mcp-server globally
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g mongodb-mcp-server --loglevel=error

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV GOOGLE_GENAI_USE_VERTEXAI=1
ENV GOOGLE_CLOUD_LOCATION=us-central1

EXPOSE 8080

# 1 worker - agent holds in-process async state; timeout 180s for Gemini
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "180", "app:app"]
