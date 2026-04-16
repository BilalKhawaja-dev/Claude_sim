"""Tests for session lifecycle management service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.orm import Conversation, Message, SessionSummary
from app.services.bedrock import BedrockError, BedrockService
from app.services.session import SessionManager


def _make_conversation(
    *,
    title: str | None = "Test Chat",
    minutes_ago: int = 0,
    days_ago: int = 0,
) -> Conversation:
    """Create a Conversation ORM object for testing."""
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago, days=days_ago)
    return Conversation(
        id=uuid.uuid4(),
        title=title,
        created_at=now,
        updated_at=now,
        last_message_at=now,
    )


def _make_message(conversation_id: uuid.UUID, role: str, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        has_image=False,
        created_at=datetime.now(timezone.utc),
    )


class TestTrackActivity:
    @pytest.mark.asyncio
    async def test_updates_last_message_at(self) -> None:
        mock_db = AsyncMock()
        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        conv_id = str(uuid.uuid4())
        await manager.track_activity(conv_id)

        mock_db.execute.assert_awaited_once()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_accepts_valid_uuid_string(self) -> None:
        mock_db = AsyncMock()
        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        conv_id = str(uuid.uuid4())
        # Should not raise
        await manager.track_activity(conv_id)


class TestCheckIdleConversations:
    @pytest.mark.asyncio
    async def test_returns_idle_conversation_ids(self) -> None:
        idle_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [idle_id]
        mock_db.execute.return_value = mock_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        result = await manager.check_idle_conversations()

        assert result == [str(idle_id)]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_idle(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        result = await manager.check_idle_conversations()
        assert result == []


class TestGenerateAndEmailSummary:
    @pytest.mark.asyncio
    async def test_generates_and_stores_summary(self) -> None:
        conv = _make_conversation(title="My Chat")
        msg = _make_message(conv.id, "user", "Hello")

        mock_db = AsyncMock()
        mock_db.get.return_value = conv

        # Mock message query result
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]
        mock_db.execute.return_value = msg_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        mock_bedrock.generate_summary.return_value = "Summary of conversation"
        mock_bedrock.generate_embedding.return_value = [0.1] * 1536

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        with patch("app.services.session.EmailService", create=True) as mock_email_cls:
            mock_email_instance = AsyncMock()
            mock_email_cls.return_value = mock_email_instance

            # Patch the import inside the method
            with patch.dict("sys.modules", {"app.services.email": MagicMock(EmailService=mock_email_cls)}):
                await manager.generate_and_email_summary(str(conv.id))

        mock_bedrock.generate_summary.assert_awaited_once()
        mock_bedrock.generate_embedding.assert_awaited_once_with("Summary of conversation")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stores_summary_even_if_email_fails(self) -> None:
        """Requirement 6.6: summary persisted regardless of email outcome."""
        conv = _make_conversation(title="My Chat")
        msg = _make_message(conv.id, "user", "Hello")

        mock_db = AsyncMock()
        mock_db.get.return_value = conv

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]
        mock_db.execute.return_value = msg_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        mock_bedrock.generate_summary.return_value = "Summary text"
        mock_bedrock.generate_embedding.return_value = [0.1] * 1536

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        # Email import will fail (ImportError), but summary should still be stored
        await manager.generate_and_email_summary(str(conv.id))

        # Summary was added and committed
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_if_conversation_not_found(self) -> None:
        mock_db = AsyncMock()
        mock_db.get.return_value = None

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        await manager.generate_and_email_summary(str(uuid.uuid4()))

        mock_bedrock.generate_summary.assert_not_awaited()
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_if_no_messages(self) -> None:
        conv = _make_conversation()

        mock_db = AsyncMock()
        mock_db.get.return_value = conv

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = msg_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        await manager.generate_and_email_summary(str(conv.id))

        mock_bedrock.generate_summary.assert_not_awaited()
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_on_bedrock_summary_failure(self) -> None:
        conv = _make_conversation()
        msg = _make_message(conv.id, "user", "Hello")

        mock_db = AsyncMock()
        mock_db.get.return_value = conv

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]
        mock_db.execute.return_value = msg_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        mock_bedrock.generate_summary.side_effect = BedrockError("BEDROCK_ERROR", "fail")

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        await manager.generate_and_email_summary(str(conv.id))

        mock_db.add.assert_not_called()


class TestRunExpiryJob:
    @pytest.mark.asyncio
    async def test_archives_expired_conversations(self) -> None:
        conv = _make_conversation(title="Old Chat", days_ago=31)
        msg = _make_message(conv.id, "user", "Old message")

        mock_db = AsyncMock()

        # First execute: find expired conversations
        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = [conv]

        # Second execute: check existing summary (none found)
        summary_check_result = MagicMock()
        summary_check_result.scalar_one_or_none.return_value = None

        # Third execute: load messages
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]

        mock_db.execute.side_effect = [expired_result, summary_check_result, msg_result]

        mock_bedrock = AsyncMock(spec=BedrockService)
        mock_bedrock.generate_summary.return_value = "Archived summary"
        mock_bedrock.generate_embedding.return_value = [0.1] * 1536

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # Summary was added
        mock_db.add.assert_called_once()
        # Conversation was deleted
        mock_db.delete.assert_awaited_once_with(conv)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_summary_if_already_exists(self) -> None:
        conv = _make_conversation(title="Old Chat", days_ago=31)

        mock_db = AsyncMock()

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = [conv]

        # Summary already exists
        summary_check_result = MagicMock()
        summary_check_result.scalar_one_or_none.return_value = uuid.uuid4()

        mock_db.execute.side_effect = [expired_result, summary_check_result]

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        await manager.run_expiry_job()

        # No summary generation needed
        mock_bedrock.generate_summary.assert_not_awaited()
        # But conversation still deleted
        mock_db.delete.assert_awaited_once_with(conv)

    @pytest.mark.asyncio
    async def test_no_expired_conversations(self) -> None:
        mock_db = AsyncMock()

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = expired_result

        mock_bedrock = AsyncMock(spec=BedrockService)
        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        await manager.run_expiry_job()

        mock_db.delete.assert_not_awaited()
        # commit is not called when there's nothing to process
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_deletion_on_summary_generation_failure(self) -> None:
        conv = _make_conversation(title="Old Chat", days_ago=31)
        msg = _make_message(conv.id, "user", "Old message")

        mock_db = AsyncMock()

        expired_result = MagicMock()
        expired_result.scalars.return_value.all.return_value = [conv]

        summary_check_result = MagicMock()
        summary_check_result.scalar_one_or_none.return_value = None

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]

        mock_db.execute.side_effect = [expired_result, summary_check_result, msg_result]

        mock_bedrock = AsyncMock(spec=BedrockService)
        mock_bedrock.generate_summary.side_effect = BedrockError("BEDROCK_ERROR", "fail")

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # Conversation should NOT be deleted if summary generation fails
        mock_db.delete.assert_not_awaited()
