FROM python:3.13-slim AS builder

ARG EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
ARG CODE_EMBEDDING_MODEL=nomic-ai/CodeRankEmbed
ARG DUAL_EMBEDDING=true
ARG ENABLE_GPU=false

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN if [ "$ENABLE_GPU" = "true" ]; then \
        pip install --no-cache-dir --prefix=/install -r requirements.txt torch; \
    else \
        pip install --no-cache-dir --prefix=/install -r requirements.txt; \
    fi

ENV PYTHONPATH=/install/lib/python3.13/site-packages
RUN python -c "\
import sys; sys.path.insert(0, '/install/lib/python3.13/site-packages'); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${EMBEDDING_MODEL}', trust_remote_code=True); \
print('Primary model downloaded')"

RUN if [ "$DUAL_EMBEDDING" = "true" ]; then \
        python -c "\
import sys; sys.path.insert(0, '/install/lib/python3.13/site-packages'); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${CODE_EMBEDDING_MODEL}', trust_remote_code=True); \
print('Code model downloaded')"; \
    fi

# ── Runtime stage ──
FROM python:3.13-slim AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends gnupg curl && \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      postgresql-17 \
      postgresql-17-pgvector && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

COPY src/ src/
COPY pyproject.toml .
COPY .env.example .env
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=stdio

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD if [ "$MCP_TRANSPORT" = "streamable-http" ]; then \
        python -c "import urllib.request; urllib.request.urlopen('http://localhost:${MCP_PORT:-8080}/health')"; \
    else \
        true; \
    fi

ENTRYPOINT ["/docker-entrypoint.sh"]
