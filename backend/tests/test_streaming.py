"""Tests for SSE streaming utilities."""

import json

import pytest

from app.utils.streaming import (
    create_streaming_response,
    sse_chunk,
    sse_done,
    sse_error,
    sse_event,
)


class TestSseEvent:
    """Unit tests for sse_event formatting."""

    def test_basic_dict(self) -> None:
        result = sse_event({"type": "chunk", "text": "hello"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        payload = json.loads(result[len("data: ") : -2])
        assert payload == {"type": "chunk", "text": "hello"}

    def test_empty_dict(self) -> None:
        result = sse_event({})
        payload = json.loads(result[len("data: ") : -2])
        assert payload == {}

    def test_nested_dict(self) -> None:
        data = {"type": "error", "details": {"code": 500}}
        result = sse_event(data)
        payload = json.loads(result[len("data: ") : -2])
        assert payload == data


class TestSseHelpers:
    """Unit tests for convenience SSE helpers."""

    def test_sse_chunk(self) -> None:
        result = sse_chunk("hello world")
        payload = json.loads(result[len("data: ") : -2])
        assert payload == {"type": "chunk", "text": "hello world"}

    def test_sse_error_default_code(self) -> None:
        result = sse_error("something broke")
        payload = json.loads(result[len("data: ") : -2])
        assert payload["type"] == "error"
        assert payload["error_code"] == "STREAM_ERROR"
        assert payload["message"] == "something broke"

    def test_sse_error_custom_code(self) -> None:
        result = sse_error("timeout", error_code="BEDROCK_TIMEOUT")
        payload = json.loads(result[len("data: ") : -2])
        assert payload["error_code"] == "BEDROCK_TIMEOUT"

    def test_sse_done(self) -> None:
        result = sse_done()
        payload = json.loads(result[len("data: ") : -2])
        assert payload == {"type": "done"}


class TestCreateStreamingResponse:
    """Tests for the full streaming response pipeline."""

    @pytest.mark.asyncio
    async def test_streams_chunks_then_done(self) -> None:
        async def gen():
            yield "Hello"
            yield " world"

        response = create_streaming_response(gen())
        assert response.media_type == "text/event-stream"

        events: list[str] = []
        async for chunk in response.body_iterator:
            events.append(chunk)

        assert len(events) == 3  # 2 chunks + done

        p0 = json.loads(events[0][len("data: ") : -2])
        assert p0 == {"type": "chunk", "text": "Hello"}

        p1 = json.loads(events[1][len("data: ") : -2])
        assert p1 == {"type": "chunk", "text": " world"}

        p2 = json.loads(events[2][len("data: ") : -2])
        assert p2 == {"type": "done"}

    @pytest.mark.asyncio
    async def test_error_during_stream(self) -> None:
        async def gen():
            yield "partial"
            raise RuntimeError("connection lost")

        response = create_streaming_response(gen())
        events: list[str] = []
        async for chunk in response.body_iterator:
            events.append(chunk)

        # Should get the partial chunk then an error event
        assert len(events) == 2
        p0 = json.loads(events[0][len("data: ") : -2])
        assert p0["type"] == "chunk"

        p1 = json.loads(events[1][len("data: ") : -2])
        assert p1["type"] == "error"
        assert "connection lost" in p1["message"]

    @pytest.mark.asyncio
    async def test_empty_generator(self) -> None:
        async def gen():
            return
            yield  # noqa: unreachable — makes this an async generator

        response = create_streaming_response(gen())
        events: list[str] = []
        async for chunk in response.body_iterator:
            events.append(chunk)

        assert len(events) == 1
        p0 = json.loads(events[0][len("data: ") : -2])
        assert p0 == {"type": "done"}

    @pytest.mark.asyncio
    async def test_response_headers(self) -> None:
        async def gen():
            yield "x"

        response = create_streaming_response(gen())
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"
