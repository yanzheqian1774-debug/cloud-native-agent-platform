FROM node:22.23.1-bookworm-slim AS openclaw

WORKDIR /opt/openclaw

COPY operator/openclaw/package.json operator/openclaw/package-lock.json ./

RUN npm ci --omit=dev \
    && npm cache clean --force

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/operator/src:/app/core/src:/app/gateway/src:/app/runtime/src

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install \
    --no-cache-dir \
    --timeout 300 \
    --retries 5 \
    uv \
    && uv sync --frozen --no-dev

COPY --from=openclaw /usr/local/bin/node /usr/local/bin/node
COPY --from=openclaw /opt/openclaw /opt/openclaw

COPY core/src ./core/src
COPY gateway/src ./gateway/src
COPY operator/src ./operator/src
COPY runtime/src ./runtime/src

ENV OPENCLAW_NODE_EXECUTABLE=/usr/local/bin/node
ENV OPENCLAW_ENTRYPOINT=/opt/openclaw/node_modules/openclaw/openclaw.mjs

USER nobody

CMD ["/app/.venv/bin/kopf", "run", "/app/operator/src/agent_operator/main.py", "--all-namespaces"]
