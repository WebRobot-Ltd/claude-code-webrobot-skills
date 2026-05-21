# WebRobot MCP server — online demo deploy
# Same image runs the local plugin variant (stdio) and the k8s variant (http)
# — entry point is selected via env vars at runtime.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user — k8s manifest runs with runAsNonRoot.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin mcp

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./

USER mcp

# Online deploy defaults — overridden via k8s env if needed.
ENV MCP_TRANSPORT=http \
    MCP_SCOPE=demo \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    MCP_PATH=/mcp \
    WEBROBOT_API_ENDPOINT=https://api.webrobot.eu

EXPOSE 8080

# Liveness/readiness use /health which the server registers via @custom_route.
CMD ["python", "-u", "server.py"]
