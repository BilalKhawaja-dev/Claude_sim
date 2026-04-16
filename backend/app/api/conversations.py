"""Conversation CRUD endpoints.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 7.6
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import User, get_current_user, get_db
from app.models.orm import Conversation, Message
from app.models.schemas import ConversationDetail, ConversationSummary, MessageResponse

router = APIRouter()


@router.post("/api/conversations", response_model=ConversationSummary)
async def create_conversation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummary:
    """Create a new conversation and return its summary."""
    conv = Conversation(id=uuid.uuid4())
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return ConversationSummary(
        id=str(conv.id),
        title=conv.title,
        updated_at=conv.updated_at,
    )


@router.get("/api/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """List conversations within the retention window, ordered by updated_at DESC."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.conversation_retention_days)

    result = await db.execute(
        select(Conversation)
        .where(Conversation.last_message_at >= cutoff)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()

    return [
        ConversationSummary(
            id=str(c.id),
            title=c.title,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """Get a conversation with its full message history."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)

    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                has_image=m.has_image,
                created_at=m.created_at,
            )
            for m in sorted_messages
        ],
    )


@router.delete("/api/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation. Cascade handles messages and embeddings."""
    conv = await db.get(Conversation, conversation_id)

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await db.delete(conv)
    await db.commit()
