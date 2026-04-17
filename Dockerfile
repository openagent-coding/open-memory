FROM python:3.13-slim AS builder

ARG EMBEDDING_MODEL=google/embeddinggemma-300m
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

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

COPY src/ src/
COPY pyproject.toml .

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=stdio

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD if [ "$MCP_TRANSPORT" = "streamable-http" ]; then \
        python -c "import urllib.request; urllib.request.urlopen('http://localhost:${MCP_PORT:-8080}/health')"; \
    else \
        true; \
    fi

ENTRYPOINT ["python", "-m", "src.server"]
