"""Tests for conversation CRUD endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)
from app.core.dependencies import User
from app.models.orm import Conversation, Message


@pytest.fixture
def mock_user() -> User:
    return User(sub="test-user-id", email="test@example.com")


def _make_conversation(
    *,
    title: str | None = "Test Chat",
    days_ago: int = 0,
) -> Conversation:
    """Create a Conversation ORM object for testing."""
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    conv = Conversation(
        id=uuid.uuid4(),
        title=title,
        created_at=now,
        updated_at=now,
        last_message_at=now,
    )
    return conv


def _make_message(conversation_id: uuid.UUID, role: str, content: str, minutes_offset: int = 0) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        has_image=False,
        created_at=datetime(2024, 1, 1, 0, minutes_offset, tzinfo=timezone.utc),
    )


class TestCreateConversation:
    @pytest.mark.asyncio
    async def test_creates_and_returns_summary(self, mock_user: User) -> None:
        mock_db = AsyncMock()

        async def fake_refresh(obj: Conversation) -> None:
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = fake_refresh

        result = await create_conversation(user=mock_user, db=mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert result.id is not None
        assert result.title is None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_returns_conversation_summary_type(self, mock_user: User) -> None:
        mock_db = AsyncMock()

        async def fake_refresh(obj: Conversation) -> None:
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = fake_refresh

        from app.models.schemas import ConversationSummary

        result = await create_conversation(user=mock_user, db=mock_db)
        assert isinstance(result, ConversationSummary)


class TestListConversations:
    @pytest.mark.asyncio
    async def test_returns_recent_conversations(self, mock_user: User) -> None:
        conv1 = _make_conversation(title="Recent", days_ago=1)
        conv2 = _make_conversation(title="Also Recent", days_ago=5)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [conv1, conv2]
        mock_db.execute.return_value = mock_result

        result = await list_conversations(user=mock_user, db=mock_db)

        assert len(result) == 2
        assert result[0].title == "Recent"
        assert result[1].title == "Also Recent"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_conversations(self, mock_user: User) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_conversations(user=mock_user, db=mock_db)
        assert result == []


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_returns_conversation_with_messages(self, mock_user: User) -> None:
        conv = _make_conversation(title="My Chat")
        msg1 = _make_message(conv.id, "user", "Hello", minutes_offset=0)
        msg2 = _make_message(conv.id, "assistant", "Hi!", minutes_offset=1)
        conv.messages = [msg2, msg1]  # intentionally unordered

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = conv
        mock_db.execute.return_value = mock_result

        result = await get_conversation(
            conversation_id=conv.id, user=mock_user, db=mock_db
        )

        assert result.id == str(conv.id)
        assert result.title == "My Chat"
        assert len(result.messages) == 2
        # Should be sorted by created_at
        assert result.messages[0].content == "Hello"
        assert result.messages[1].content == "Hi!"

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_conversation(self, mock_user: User) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_conversation(
                conversation_id=uuid.uuid4(), user=mock_user, db=mock_db
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_message_history(self, mock_user: User) -> None:
        conv = _make_conversation(title="Empty Chat")
        conv.messages = []

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = conv
        mock_db.execute.return_value = mock_result

        result = await get_conversation(
            conversation_id=conv.id, user=mock_user, db=mock_db
        )
        assert result.messages == []


class TestDeleteConversation:
    @pytest.mark.asyncio
    async def test_deletes_existing_conversation(self, mock_user: User) -> None:
        conv = _make_conversation()

        mock_db = AsyncMock()
        mock_db.get.return_value = conv

        await delete_conversation(
            conversation_id=conv.id, user=mock_user, db=mock_db
        )

        mock_db.delete.assert_awaited_once_with(conv)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_conversation(self, mock_user: User) -> None:
        mock_db = AsyncMock()
        mock_db.get.return_value = None

        with pytest.raises(Exception) as exc_info:
            await delete_conversation(
                conversation_id=uuid.uuid4(), user=mock_user, db=mock_db
            )
        assert exc_info.value.status_code == 404
