"""POST /api/chat endpoint — streaming chat with RAG context.

Validates: Requirements 1.1, 1.2, 1.5, 3.5, 4.1, 4.2, 4.3, 4.4, 6.1, 6.5
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import boto3
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.core.dependencies import User, get_current_user, get_db
from app.models.orm import Conversation, Message
from app.models.schemas import ChatRequest, ErrorResponse
from app.services.bedrock import BedrockError, BedrockService
from app.services.rag import RAGService
from app.utils.streaming import create_streaming_response, sse_chunk, sse_done, sse_error

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level service singleton (stateless, safe to share)
_bedrock = BedrockService()

TITLE_GENERATION_PROMPT = (
    "Generate a short, descriptive title (max 6 words) for a conversation "
    "that starts with the following message. Return ONLY the title text, "
    "no quotes, no punctuation at the end."
)


async def _generate_title(user_message: str) -> str:
    """Ask Bedrock to produce a short conversation title from the first message."""
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 30,
            "system": TITLE_GENERATION_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        })
        client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        response = client.invoke_model(
            modelId="anthropic.claude-sonnet-4-20250514",
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        blocks = result.get("content", [])
        title = "".join(b["text"] for b in blocks if b.get("type") == "text").strip()
        return title[:255] if title else "New conversation"
    except Exception:
        logger.exception("Failed to generate conversation title")
        return "New conversation"


async def _build_history_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> list[dict]:
    """Load conversation history as Anthropic-format messages."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    rows = result.scalars().all()
    messages: list[dict] = []
    for msg in rows:
        content: list[dict] | str = msg.content
        if msg.has_image and msg.image_data:
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": msg.image_data,
                    },
                },
                {"type": "text", "text": msg.content},
            ]
        messages.append({"role": msg.role, "content": content})
    return messages


def _build_system_prompt(rag_chunks: list) -> str:
    """Build the system prompt, injecting RAG context when available."""
    base = (
        "You are Claude, an AI assistant made by Anthropic. "
        "Be helpful, harmless, and honest."
    )
    if not rag_chunks:
        return base

    context_parts = [f"- {r.chunk_text}" for r in rag_chunks]
    context_block = "\n".join(context_parts)
    return (
        f"{base}\n\n"
        "The following context was retrieved from memory and may be relevant "
        "to the user's question. Use it if helpful:\n"
        f"{context_block}"
    )


@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a chat response with RAG-augmented context.

    Flow:
    1. Validate conversation exists
    2. Store user message
    3. Generate embedding of user message
    4. RAG-retrieve relevant context (top-5, cosine >= 0.7)
    5. Build prompt with conversation history + RAG context
    6. Stream Bedrock response via SSE
    7. After stream: store assistant message, chunk+embed exchange
    8. Auto-generate title if first message
    9. Update last_message_at on conversation
    """
    conversation_id = uuid.UUID(request.conversation_id)

    # --- 1. Validate conversation ---
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # --- 2. Store user message ---
    user_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=request.message,
        has_image=request.image is not None,
        image_data=request.image,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()

    # --- 3. Generate embedding of user message ---
    try:
        query_embedding = await _bedrock.generate_embedding(request.message)
    except BedrockError:
        logger.exception("Failed to generate embedding for user message")
        query_embedding = None

    # --- 4. RAG retrieve context ---
    rag_results = []
    if query_embedding is not None:
        try:
            rag_service = RAGService(db=db, bedrock=_bedrock)
            rag_results = await rag_service.retrieve_context(
                query_embedding=query_embedding, top_k=5, threshold=0.7
            )
        except Exception:
            logger.exception("RAG retrieval failed, proceeding without context")

    # --- 5. Build prompt ---
    history = await _build_history_messages(db, conversation_id)
    system_prompt = _build_system_prompt(rag_results)

    # --- Determine if this is the first message (for title generation) ---
    is_first_message = conv.title is None

    # --- 6 & 7. Stream response, then persist ---
    async def _stream_and_persist() -> AsyncGenerator[str, None]:
        """Yield SSE events while collecting the full response for persistence."""
        full_response: list[str] = []
        try:
            async for chunk_text in _bedrock.stream_chat(
                messages=history,
                model=request.model.value,
                system_prompt=system_prompt,
            ):
                full_response.append(chunk_text)
                yield sse_chunk(chunk_text)

            yield sse_done()
        except BedrockError as exc:
            yield sse_error(exc.message, exc.error_code)
            return

        # --- Post-stream persistence (runs after all chunks sent) ---
        assistant_text = "".join(full_response)

        try:
            # Store assistant message
            assistant_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_text,
                has_image=False,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_msg)

            # Update last_message_at for idle tracking
            await db.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(
                    last_message_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )

            # Auto-generate title from first message
            if is_first_message:
                title = await _generate_title(request.message)
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == conversation_id)
                    .values(title=title)
                )

            # Chunk + embed the exchange
            try:
                rag_service = RAGService(db=db, bedrock=_bedrock)
                await rag_service.store_exchange(
                    conversation_id=str(conversation_id),
                    user_text=request.message,
                    assistant_text=assistant_text,
                )
            except Exception:
                logger.exception("Failed to chunk+embed exchange")

            await db.commit()
        except Exception:
            logger.exception("Failed to persist assistant message")
            await db.rollback()

    return StreamingResponse(
        _stream_and_persist(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
