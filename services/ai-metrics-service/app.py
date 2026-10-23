"""HTTP service that emits synthetic AI workload metrics for cost demonstrations."""

from time import perf_counter, sleep

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI(title="AI Metrics Service", version="1.0.0")

REQUEST_COUNT = Counter(
    "request_count",
    "Number of inference requests processed.",
    ["service", "model", "status"],
)
TOKEN_COUNT = Counter(
    "token_count",
    "Number of input and output tokens processed.",
    ["service", "model", "token_type"],
)
RESPONSE_LATENCY = Histogram(
    "response_latency_seconds",
    "End-to-end inference response latency in seconds.",
    ["service", "model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


class InferenceRequest(BaseModel):
    """A synthetic inference request used to create metric samples."""

    service: str = Field(default="customer-chat", min_length=1)
    model: str = Field(default="demo-model", min_length=1)
    input_tokens: int = Field(default=100, ge=0)
    output_tokens: int = Field(default=50, ge=0)
    processing_ms: int = Field(default=50, ge=0, le=5_000)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/infer")
def infer(request: InferenceRequest) -> dict[str, object]:
    """Simulate an AI inference request and record its cost-relevant metrics."""
    started_at = perf_counter()
    try:
        sleep(request.processing_ms / 1_000)
        TOKEN_COUNT.labels(
            service=request.service, model=request.model, token_type="input"
        ).inc(request.input_tokens)
        TOKEN_COUNT.labels(
            service=request.service, model=request.model, token_type="output"
        ).inc(request.output_tokens)
        REQUEST_COUNT.labels(
            service=request.service, model=request.model, status="success"
        ).inc()
        return {
            "service": request.service,
            "model": request.model,
            "input_tokens": request.input_tokens,
            "output_tokens": request.output_tokens,
            "status": "success",
        }
    finally:
        RESPONSE_LATENCY.labels(service=request.service, model=request.model).observe(
            perf_counter() - started_at
        )
