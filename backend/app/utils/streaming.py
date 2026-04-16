"""SSE (Server-Sent Events) streaming utilities for EventSource consumption."""

import json
from collections.abc import AsyncGenerator
from typing import Any

from starlette.responses import StreamingResponse


def sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE event string.

    Args:
        data: Dictionary payload to serialize as JSON.

    Returns:
        SSE-formatted string: ``data: {json}\\n\\n``
    """
    return f"data: {json.dumps(data)}\n\n"


def sse_chunk(text: str) -> str:
    """Create an SSE event for a text chunk."""
    return sse_event({"type": "chunk", "text": text})


def sse_error(message: str, error_code: str = "STREAM_ERROR") -> str:
    """Create an SSE event for an error."""
    return sse_event({"type": "error", "error_code": error_code, "message": message})


def sse_done() -> str:
    """Create an SSE event signalling stream completion."""
    return sse_event({"type": "done"})


async def _wrap_chunks(
    chunks: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """Wrap an async generator of text chunks into SSE events.

    Yields SSE-formatted chunk events for each text piece, followed by a
    done event when the generator is exhausted. If the generator raises,
    an error event is yielded instead.
    """
    try:
        async for text in chunks:
            yield sse_chunk(text)
        yield sse_done()
    except Exception as exc:  # noqa: BLE001
        yield sse_error(str(exc))


def create_streaming_response(
    chunks: AsyncGenerator[str, None],
) -> StreamingResponse:
    """Build a ``StreamingResponse`` that streams SSE events from *chunks*.

    Args:
        chunks: Async generator yielding text strings (e.g. from Bedrock).

    Returns:
        A FastAPI/Starlette ``StreamingResponse`` with the correct
        ``text/event-stream`` content type and cache-control headers.
    """
    return StreamingResponse(
        _wrap_chunks(chunks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
