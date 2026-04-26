FROM python:3.12-slim

ENV HOME=/home/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_PATH=/mcp

WORKDIR /app

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /home/app --create-home app

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY api/ ./api/
COPY common/ ./common/
COPY config/ ./config/
COPY mcp/ ./mcp/
COPY utils/ ./utils/

COPY deployment/mcp/oci/ /home/app/.oci/

RUN chown -R app:app /app /home/app && \
    find /home/app/.oci -type d -exec chmod 700 {} \; && \
    find /home/app/.oci -type f -exec chmod 600 {} \;

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, socket; s = socket.create_connection(('127.0.0.1', int(os.getenv('MCP_PORT', '8000'))), 5); s.close()"

CMD ["sh", "-c", "uvicorn mcp_consumption:app --app-dir mcp --host ${MCP_HOST} --port ${MCP_PORT}"]
