"""Native Agent Runtime."""

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Enterprise Agent Runtime",
    version="0.1.0",
)


class InvokeRequest(BaseModel):
    """Agent invocation request."""

    input: str


class InvokeResponse(BaseModel):
    """Agent invocation response."""

    output: str
    agent: str
    model: str


def runtime_info() -> dict[str, Any]:
    """Return runtime identity and configuration."""

    return {
        "agent": os.getenv("AGENT_NAME", "unknown"),
        "namespace": os.getenv("AGENT_NAMESPACE", "unknown"),
        "runtime": os.getenv("AGENT_RUNTIME", "native"),
        "model_provider": os.getenv("MODEL_PROVIDER", "mock"),
        "model": os.getenv("MODEL_NAME", "mock-model"),
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness endpoint."""

    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    """Readiness endpoint."""

    return {"status": "ready"}


@app.get("/v1/info")
def info() -> dict[str, Any]:
    """Return runtime information."""

    return runtime_info()


@app.post("/v1/invoke")
def invoke(request: InvokeRequest) -> InvokeResponse:
    """Execute a mock Agent invocation."""

    runtime = runtime_info()

    return InvokeResponse(
        output=f"mock response: {request.input}",
        agent=runtime["agent"],
        model=runtime["model"],
    )
