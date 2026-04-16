# Feature: claude-simulator, Property 12: User memory CRUD round-trip
# Validates: Requirements 5.2, 5.3
"""
Property-based test verifying that user memory entries created or updated
via the memory API endpoints return the same text content on retrieval,
and that the stored embedding is always a valid 1536-dimensional vector.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.memory import create_memory, list_memory, update_memory
from app.core.dependencies import User
from app.models.orm import UserMemory
from app.models.schemas import MemoryCreateRequest, MemoryUpdateRequest

# --- Strategies ---

# Non-empty text content (MemoryCreateRequest enforces min_length=1)
memory_content_strategy = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())


def _deterministic_embedding(text: str) -> list[float]:
    """Return a deterministic 1536-dim vector based on text length."""
    seed = len(text) % 100 / 100.0
    return [seed + (i / 1536.0) for i in range(1536)]


def _make_mock_db_for_create(embedding: list[float]) -> AsyncMock:
    """Create a mock DB session that captures the added UserMemory object."""
    mock_db = AsyncMock()
    captured: dict[str, UserMemory | None] = {"entry": None}

    def capture_add(obj: UserMemory) -> None:
        captured["entry"] = obj

    mock_db.add = MagicMock(side_effect=capture_add)

    async def fake_refresh(obj: UserMemory) -> None:
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if obj.updated_at is None:
            obj.updated_at = datetime.now(timezone.utc)

    mock_db.refresh = fake_refresh
    mock_db._captured = captured
    return mock_db


def _make_mock_db_for_list(entries: list[UserMemory]) -> AsyncMock:
    """Create a mock DB session that returns the given entries on list."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = entries
    mock_db.execute.return_value = mock_result
    return mock_db


def _make_mock_db_for_update(existing: UserMemory) -> AsyncMock:
    """Create a mock DB session that returns an existing entry for update."""
    mock_db = AsyncMock()
    mock_db.get.return_value = existing

    async def fake_refresh(obj: UserMemory) -> None:
        pass

    mock_db.refresh = fake_refresh
    return mock_db


MOCK_USER = User(sub="test-user", email="test@example.com")


class TestPropertyMemoryCRUDRoundTrip:
    """Property 12: User memory CRUD round-trip."""

    @settings(max_examples=50)
    @given(content=memory_content_strategy)
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_create_then_list_returns_same_content(
        self, mock_bedrock: MagicMock, content: str
    ) -> None:
        """**Validates: Requirements 5.2**

        For any text content, creating a memory entry and then listing
        entries SHALL return the same content text.
        """
        embedding = _deterministic_embedding(content)
        mock_bedrock.generate_embedding = AsyncMock(return_value=embedding)

        # Create
        create_db = _make_mock_db_for_create(embedding)
        req = MemoryCreateRequest(content=content)
        created = await create_memory(entry=req, user=MOCK_USER, db=create_db)

        assert created.content == content

        # Simulate listing by building a UserMemory from what was created
        now = datetime.now(timezone.utc)
        stored_entry = UserMemory(
            id=uuid.UUID(created.id),
            content=content,
            embedding=embedding,
            created_at=now,
            updated_at=now,
        )
        list_db = _make_mock_db_for_list([stored_entry])
        entries = await list_memory(user=MOCK_USER, db=list_db)

        assert len(entries) == 1
        assert entries[0].content == content

    @settings(max_examples=50)
    @given(
        original=memory_content_strategy,
        updated_text=memory_content_strategy,
    )
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_update_reflects_new_content(
        self, mock_bedrock: MagicMock, original: str, updated_text: str
    ) -> None:
        """**Validates: Requirements 5.3**

        For any text content update, the updated entry SHALL reflect
        the new content.
        """
        new_embedding = _deterministic_embedding(updated_text)
        mock_bedrock.generate_embedding = AsyncMock(return_value=new_embedding)

        now = datetime.now(timezone.utc)
        existing = UserMemory(
            id=uuid.uuid4(),
            content=original,
            embedding=_deterministic_embedding(original),
            created_at=now,
            updated_at=now,
        )

        mock_db = _make_mock_db_for_update(existing)
        req = MemoryUpdateRequest(content=updated_text)
        result = await update_memory(
            entry_id=existing.id, entry=req, user=MOCK_USER, db=mock_db
        )

        assert result.content == updated_text
        # The underlying ORM object should also be mutated
        assert existing.content == updated_text

    @settings(max_examples=50)
    @given(content=memory_content_strategy)
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_created_embedding_is_1536_dimensional(
        self, mock_bedrock: MagicMock, content: str
    ) -> None:
        """**Validates: Requirements 5.2**

        For any created memory entry, the stored embedding SHALL be a
        valid 1536-dimensional vector.
        """
        embedding = _deterministic_embedding(content)
        mock_bedrock.generate_embedding = AsyncMock(return_value=embedding)

        create_db = _make_mock_db_for_create(embedding)
        req = MemoryCreateRequest(content=content)
        await create_memory(entry=req, user=MOCK_USER, db=create_db)

        # Verify the ORM object that was added to the session
        added_obj = create_db.add.call_args[0][0]
        assert isinstance(added_obj.embedding, list)
        assert len(added_obj.embedding) == 1536
        assert all(isinstance(v, (int, float)) for v in added_obj.embedding)

    @settings(max_examples=50)
    @given(
        original=memory_content_strategy,
        updated_text=memory_content_strategy,
    )
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_updated_embedding_is_1536_dimensional(
        self, mock_bedrock: MagicMock, original: str, updated_text: str
    ) -> None:
        """**Validates: Requirements 5.3**

        For any updated memory entry, the regenerated embedding SHALL be
        a valid 1536-dimensional vector corresponding to the new text.
        """
        new_embedding = _deterministic_embedding(updated_text)
        mock_bedrock.generate_embedding = AsyncMock(return_value=new_embedding)

        now = datetime.now(timezone.utc)
        existing = UserMemory(
            id=uuid.uuid4(),
            content=original,
            embedding=_deterministic_embedding(original),
            created_at=now,
            updated_at=now,
        )

        mock_db = _make_mock_db_for_update(existing)
        req = MemoryUpdateRequest(content=updated_text)
        await update_memory(
            entry_id=existing.id, entry=req, user=MOCK_USER, db=mock_db
        )

        assert isinstance(existing.embedding, list)
        assert len(existing.embedding) == 1536
        assert all(isinstance(v, (int, float)) for v in existing.embedding)
        # Embedding should correspond to the updated text
        assert existing.embedding == new_embedding
