"""User memory CRUD endpoints.

Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import User, get_current_user, get_db
from app.models.orm import UserMemory
from app.models.schemas import MemoryCreateRequest, MemoryUpdateRequest, UserMemoryEntry
from app.services.bedrock import BedrockError, BedrockService

logger = logging.getLogger(__name__)

router = APIRouter()

_bedrock = BedrockService()


@router.get("/api/memory", response_model=list[UserMemoryEntry])
async def list_memory(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserMemoryEntry]:
    """Get all user memory entries."""
    result = await db.execute(
        select(UserMemory).order_by(UserMemory.created_at.desc())
    )
    entries = result.scalars().all()

    return [
        UserMemoryEntry(
            id=str(e.id),
            content=e.content,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in entries
    ]


@router.post("/api/memory", response_model=UserMemoryEntry, status_code=status.HTTP_201_CREATED)
async def create_memory(
    entry: MemoryCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMemoryEntry:
    """Create a memory entry with embedding."""
    try:
        embedding = await _bedrock.generate_embedding(entry.content)
    except BedrockError as exc:
        logger.error("Failed to generate embedding for memory entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding generation failed: {exc.message}",
        ) from exc

    now = datetime.now(timezone.utc)
    memory = UserMemory(
        id=uuid.uuid4(),
        content=entry.content,
        embedding=embedding,
        created_at=now,
        updated_at=now,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    return UserMemoryEntry(
        id=str(memory.id),
        content=memory.content,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.put("/api/memory/{entry_id}", response_model=UserMemoryEntry)
async def update_memory(
    entry_id: uuid.UUID,
    entry: MemoryUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMemoryEntry:
    """Update a memory entry and regenerate its embedding."""
    memory = await db.get(UserMemory, entry_id)
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory entry not found",
        )

    try:
        embedding = await _bedrock.generate_embedding(entry.content)
    except BedrockError as exc:
        logger.error("Failed to regenerate embedding for memory entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding generation failed: {exc.message}",
        ) from exc

    memory.content = entry.content
    memory.embedding = embedding
    memory.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(memory)

    return UserMemoryEntry(
        id=str(memory.id),
        content=memory.content,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.delete("/api/memory/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a memory entry and its embedding."""
    memory = await db.get(UserMemory, entry_id)
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory entry not found",
        )

    await db.delete(memory)
    await db.commit()
