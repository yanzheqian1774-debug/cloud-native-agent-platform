FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/operator/src

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install \
    --no-cache-dir \
    --timeout 300 \
    --retries 5 \
    uv \
    && uv sync --frozen --no-dev

COPY operator ./operator

CMD ["/app/.venv/bin/kopf", "run", "/app/operator/src/agent_operator/main.py", "--all-namespaces"]
