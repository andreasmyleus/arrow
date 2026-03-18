FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Download embedding model at build time (cached in layer)
RUN python -c "from arrow.embedder import Embedder; e = Embedder(); e.download_model()"

# --- Runtime stage ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/arrow /usr/local/bin/arrow
COPY --from=builder /app/src /app/src

# Copy cached model from builder
COPY --from=builder /root/.arrow/models /root/.arrow/models

ENV ARROW_DB_PATH=/data/index.db
ENV ARROW_VECTOR_PATH=/data/vectors.usearch

VOLUME ["/data", "/workspace"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/mcp')" || exit 1

ENTRYPOINT ["python", "-m", "arrow"]
CMD ["--transport", "http", "--port", "8080"]
