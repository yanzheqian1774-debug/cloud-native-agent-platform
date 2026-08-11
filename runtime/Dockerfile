FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --locked \
    --no-dev \
    --no-install-project

COPY runtime/src /app/runtime/src

ENV PYTHONPATH=/app/runtime/src \
    AGENT_NAME=unknown \
    AGENT_NAMESPACE=unknown \
    AGENT_RUNTIME=native \
    MODEL_PROVIDER=mock \
    MODEL_NAME=mock-model

EXPOSE 8080

USER nobody

CMD ["/app/.venv/bin/uvicorn", \
     "agent_runtime.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080"]
