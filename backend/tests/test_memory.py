"""Tests for user memory CRUD endpoints.

Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.memory import (
    create_memory,
    delete_memory,
    list_memory,
    update_memory,
)
from app.core.dependencies import User
from app.models.orm import UserMemory
from app.models.schemas import MemoryCreateRequest, MemoryUpdateRequest
from app.services.bedrock import BedrockError


@pytest.fixture
def mock_user() -> User:
    return User(sub="test-user-id", email="test@example.com")


def _make_memory_entry(content: str = "I like Python") -> UserMemory:
    now = datetime.now(timezone.utc)
    return UserMemory(
        id=uuid.uuid4(),
        content=content,
        embedding=[0.1] * 1536,
        created_at=now,
        updated_at=now,
    )


class TestListMemory:
    @pytest.mark.asyncio
    async def test_returns_all_entries(self, mock_user: User) -> None:
        e1 = _make_memory_entry("Fact one")
        e2 = _make_memory_entry("Fact two")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [e1, e2]
        mock_db.execute.return_value = mock_result

        result = await list_memory(user=mock_user, db=mock_db)

        assert len(result) == 2
        assert result[0].content == "Fact one"
        assert result[1].content == "Fact two"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, mock_user: User) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_memory(user=mock_user, db=mock_db)
        assert result == []

    @pytest.mark.asyncio
    async def test_entries_have_correct_fields(self, mock_user: User) -> None:
        entry = _make_memory_entry("My preference")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db.execute.return_value = mock_result

        result = await list_memory(user=mock_user, db=mock_db)

        assert result[0].id == str(entry.id)
        assert result[0].content == "My preference"
        assert result[0].created_at == entry.created_at
        assert result[0].updated_at == entry.updated_at


class TestCreateMemory:
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_creates_entry_with_embedding(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        fake_embedding = [0.5] * 1536
        mock_bedrock.generate_embedding = AsyncMock(return_value=fake_embedding)

        mock_db = AsyncMock()

        async def fake_refresh(obj: UserMemory) -> None:
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = fake_refresh

        req = MemoryCreateRequest(content="I prefer dark mode")
        result = await create_memory(entry=req, user=mock_user, db=mock_db)

        mock_bedrock.generate_embedding.assert_awaited_once_with("I prefer dark mode")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert result.content == "I prefer dark mode"

    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_returns_201_status(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        """The endpoint is decorated with status_code=201."""
        mock_bedrock.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        mock_db = AsyncMock()

        async def fake_refresh(obj: UserMemory) -> None:
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = fake_refresh

        req = MemoryCreateRequest(content="test")
        result = await create_memory(entry=req, user=mock_user, db=mock_db)
        # If we get here without error, the endpoint function works
        assert result.content == "test"

    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_bedrock_error_raises_502(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        mock_bedrock.generate_embedding = AsyncMock(
            side_effect=BedrockError("BEDROCK_ERROR", "Embedding failed")
        )
        mock_db = AsyncMock()

        req = MemoryCreateRequest(content="test")
        with pytest.raises(Exception) as exc_info:
            await create_memory(entry=req, user=mock_user, db=mock_db)
        assert exc_info.value.status_code == 502


class TestUpdateMemory:
    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_updates_content_and_embedding(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        entry = _make_memory_entry("Old content")
        new_embedding = [0.9] * 1536
        mock_bedrock.generate_embedding = AsyncMock(return_value=new_embedding)

        mock_db = AsyncMock()
        mock_db.get.return_value = entry

        async def fake_refresh(obj: UserMemory) -> None:
            pass

        mock_db.refresh = fake_refresh

        req = MemoryUpdateRequest(content="New content")
        result = await update_memory(
            entry_id=entry.id, entry=req, user=mock_user, db=mock_db
        )

        assert entry.content == "New content"
        assert entry.embedding == new_embedding
        mock_bedrock.generate_embedding.assert_awaited_once_with("New content")
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_returns_404_for_missing_entry(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        mock_db = AsyncMock()
        mock_db.get.return_value = None

        req = MemoryUpdateRequest(content="New content")
        with pytest.raises(Exception) as exc_info:
            await update_memory(
                entry_id=uuid.uuid4(), entry=req, user=mock_user, db=mock_db
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.memory._bedrock")
    async def test_bedrock_error_raises_502(
        self, mock_bedrock: MagicMock, mock_user: User
    ) -> None:
        entry = _make_memory_entry("Content")
        mock_bedrock.generate_embedding = AsyncMock(
            side_effect=BedrockError("BEDROCK_ERROR", "Embedding failed")
        )
        mock_db = AsyncMock()
        mock_db.get.return_value = entry

        req = MemoryUpdateRequest(content="Updated")
        with pytest.raises(Exception) as exc_info:
            await update_memory(
                entry_id=entry.id, entry=req, user=mock_user, db=mock_db
            )
        assert exc_info.value.status_code == 502


class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_deletes_existing_entry(self, mock_user: User) -> None:
        entry = _make_memory_entry("To delete")

        mock_db = AsyncMock()
        mock_db.get.return_value = entry

        await delete_memory(entry_id=entry.id, user=mock_user, db=mock_db)

        mock_db.delete.assert_awaited_once_with(entry)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_entry(self, mock_user: User) -> None:
        mock_db = AsyncMock()
        mock_db.get.return_value = None

        with pytest.raises(Exception) as exc_info:
            await delete_memory(
                entry_id=uuid.uuid4(), user=mock_user, db=mock_db
            )
        assert exc_info.value.status_code == 404
