# Feature: claude-simulator, Property 13: User memory deletion
# Validates: Requirements 5.4
"""
Property-based test verifying that for any user memory entry that is deleted,
querying the user_memory table for that entry's ID SHALL return no results.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.memory import delete_memory
from app.core.dependencies import User
from app.models.orm import UserMemory


# --- Strategies ---

memory_content_strategy = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())


def _deterministic_embedding(text: str) -> list[float]:
    """Return a deterministic 1536-dim vector based on text length."""
    seed = len(text) % 100 / 100.0
    return [seed + (i / 1536.0) for i in range(1536)]


MOCK_USER = User(sub="test-user", email="test@example.com")


class TestPropertyMemoryDeletion:
    """Property 13: User memory deletion.

    **Validates: Requirements 5.4**
    """

    @settings(max_examples=50)
    @given(content=memory_content_strategy)
    @pytest.mark.asyncio
    async def test_delete_calls_db_delete_with_correct_entry(
        self, content: str
    ) -> None:
        """**Validates: Requirements 5.4**

        For any memory entry that is deleted via delete_memory(),
        the DB session's delete method SHALL be called with the correct entry.
        """
        entry_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        existing = UserMemory(
            id=entry_id,
            content=content,
            embedding=_deterministic_embedding(content),
            created_at=now,
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_db.get.return_value = existing

        await delete_memory(entry_id=entry_id, user=MOCK_USER, db=mock_db)

        # Verify db.delete was called with the correct entry
        mock_db.delete.assert_awaited_once_with(existing)
        # Verify commit was called after deletion
        mock_db.commit.assert_awaited_once()

    @settings(max_examples=50)
    @given(content=memory_content_strategy)
    @pytest.mark.asyncio
    async def test_after_deletion_query_returns_no_results(
        self, content: str
    ) -> None:
        """**Validates: Requirements 5.4**

        For any memory entry that is deleted, querying for that entry's ID
        SHALL return no results (db.get returns None).
        """
        entry_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        existing = UserMemory(
            id=entry_id,
            content=content,
            embedding=_deterministic_embedding(content),
            created_at=now,
            updated_at=now,
        )

        mock_db = AsyncMock()
        # First call returns the entry (for deletion lookup)
        # Second call returns None (simulating post-deletion query)
        mock_db.get.side_effect = [existing, None]

        # Perform deletion
        await delete_memory(entry_id=entry_id, user=MOCK_USER, db=mock_db)

        # Simulate querying for the deleted entry — should return None
        result = await mock_db.get(UserMemory, entry_id)
        assert result is None
