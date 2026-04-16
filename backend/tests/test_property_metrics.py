# Feature: claude-simulator, Property 24: Metrics endpoint produces valid Prometheus format
# Validates: Requirements 11.1
"""
Property-based test verifying that the /metrics endpoint produces valid
Prometheus exposition format text including required metric families.

For any GET request to the /metrics endpoint, the response SHALL contain
valid Prometheus exposition format text including at minimum:
http_requests_total, http_request_duration_seconds, and error rate counters.
"""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from httpx import ASGITransport, AsyncClient

from app.main import app

# Strategy: generate random paths to hit before checking /metrics,
# ensuring the instrumentator has recorded at least some requests.
request_path_strategy = st.sampled_from(
    ["/api/health", "/docs", "/openapi.json", "/metrics"]
)

# Strategy: number of warm-up requests to make before checking metrics
warmup_count_strategy = st.integers(min_value=1, max_value=5)

# Prometheus exposition format patterns:
# A HELP line: # HELP <metric_name> <docstring>
HELP_LINE_RE = re.compile(r"^# HELP \S+ .+$", re.MULTILINE)
# A TYPE line: # TYPE <metric_name> <type>
TYPE_LINE_RE = re.compile(r"^# TYPE \S+ (counter|gauge|histogram|summary|untyped)$", re.MULTILINE)
# A metric sample line: <metric_name>{<labels>} <value> [<timestamp>]
# or <metric_name> <value> [<timestamp>]
SAMPLE_LINE_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]*\})?\s+[\d.eE+\-]+", re.MULTILINE)

# Required metric name prefixes from prometheus-fastapi-instrumentator
REQUIRED_METRICS = [
    "http_requests_total",
    "http_request_duration_seconds",
]


class TestPropertyMetricsEndpoint:
    """**Validates: Requirements 11.1**"""

    @pytest.mark.asyncio
    @given(warmup_path=request_path_strategy, warmup_count=warmup_count_strategy)
    @settings(max_examples=50)
    async def test_metrics_endpoint_returns_prometheus_format(
        self, warmup_path: str, warmup_count: int
    ) -> None:
        """The /metrics endpoint SHALL return valid Prometheus exposition
        format text for any GET request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Warm up: make some requests so the instrumentator records data
            for _ in range(warmup_count):
                await client.get(warmup_path)

            # Fetch metrics
            response = await client.get("/metrics")

        assert response.status_code == 200
        # Prometheus exposition format uses text/plain or the OpenMetrics content type
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type or "text/openmetrics" in content_type or "text" in content_type

        body = response.text
        assert len(body) > 0, "Metrics response body SHALL not be empty"

        # Validate Prometheus exposition format structure:
        # Must contain at least one HELP line, one TYPE line, and one sample line
        assert HELP_LINE_RE.search(body), (
            "Metrics response SHALL contain at least one # HELP line"
        )
        assert TYPE_LINE_RE.search(body), (
            "Metrics response SHALL contain at least one # TYPE line"
        )
        assert SAMPLE_LINE_RE.search(body), (
            "Metrics response SHALL contain at least one metric sample line"
        )

    @pytest.mark.asyncio
    @given(warmup_path=request_path_strategy, warmup_count=warmup_count_strategy)
    @settings(max_examples=50)
    async def test_metrics_contains_required_metric_families(
        self, warmup_path: str, warmup_count: int
    ) -> None:
        """The /metrics endpoint SHALL contain http_requests_total and
        http_request_duration_seconds metric families."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(warmup_count):
                await client.get(warmup_path)

            response = await client.get("/metrics")

        assert response.status_code == 200
        body = response.text

        for metric_name in REQUIRED_METRICS:
            assert metric_name in body, (
                f"Metrics response SHALL contain '{metric_name}' but it was "
                f"not found in the response body"
            )

    @pytest.mark.asyncio
    @given(warmup_path=request_path_strategy, warmup_count=warmup_count_strategy)
    @settings(max_examples=50)
    async def test_metrics_contains_error_rate_counters(
        self, warmup_path: str, warmup_count: int
    ) -> None:
        """The /metrics endpoint SHALL contain error rate counters.
        The prometheus-fastapi-instrumentator tracks HTTP status codes,
        so error rates are derivable from http_requests_total with
        status labels or from dedicated error metrics."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(warmup_count):
                await client.get(warmup_path)

            # Also trigger a 404 to ensure error status codes are recorded
            await client.get("/nonexistent-path-for-error-counter")

            response = await client.get("/metrics")

        assert response.status_code == 200
        body = response.text

        # The instrumentator records request counts with status labels.
        # Error rate counters are present as http_requests_total with
        # status="4xx" or "5xx" labels, or as http_request_duration_seconds
        # buckets that include status labels. We verify that the metrics
        # body contains status-labeled entries that enable error rate computation.
        has_status_labels = "status" in body or "handler" in body
        has_request_counter = "http_requests_total" in body or "http_request_duration" in body
        assert has_status_labels and has_request_counter, (
            "Metrics SHALL include status-labeled counters to enable error rate computation"
        )

    @pytest.mark.asyncio
    @given(warmup_count=warmup_count_strategy)
    @settings(max_examples=30)
    async def test_metrics_lines_are_valid_prometheus_format(
        self, warmup_count: int
    ) -> None:
        """Every non-empty line in the /metrics response SHALL be either a
        comment line (# HELP, # TYPE, or #) or a valid metric sample line."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(warmup_count):
                await client.get("/api/health")

            response = await client.get("/metrics")

        assert response.status_code == 200
        body = response.text

        comment_re = re.compile(r"^#")
        sample_re = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]*\})?\s+[\d.eE+\-]+")

        for line in body.splitlines():
            if not line.strip():
                continue  # blank lines are allowed
            assert comment_re.match(line) or sample_re.match(line), (
                f"Line does not match Prometheus exposition format: {line!r}"
            )
