# Feature: claude-simulator, Property 19: Expiry archival preserves summaries indefinitely
# Validates: Requirements 7.2, 7.3, 7.5
"""
Property-based test verifying that run_expiry_job() correctly archives expired
conversations by creating session_summary records and never deletes existing
session_summary records.

For any expired conversation, after the expiry job runs, a session_summary
record SHALL exist for that conversation, and the expiry job SHALL NOT delete
any records from the session_summaries table.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import settings as app_settings
from app.models.orm import Conversation, Message, SessionSummary
from app.services.bedrock import BedrockService
from app.services.session import SessionManager

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Days past the 30-day retention window (31 to 365)
days_past_expiry_st = st.integers(
    min_value=app_settings.conversation_retention_days + 1,
    max_value=365,
)

# Number of messages in the expired conversation (at least 1 so summary is generated)
message_count_st = st.integers(min_value=1, max_value=5)

# Non-empty summary text (simulates Bedrock output)
summary_text_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=300,
).filter(lambda s: s.strip())

# Whether the conversation already has a pre-existing summary
has_existing_summary_st = st.booleans()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_expired_conversation(days_past: int) -> Conversation:
    """Create a Conversation with last_message_at older than the retention window."""
    last_msg = datetime.now(timezone.utc) - timedelta(days=days_past)
    return Conversation(
        id=uuid.uuid4(),
        title="Expired chat",
        created_at=last_msg - timedelta(hours=1),
        updated_at=last_msg,
        last_message_at=last_msg,
    )


def _make_messages(conv_id: uuid.UUID, count: int) -> list[Message]:
    """Create a list of alternating user/assistant messages for a conversation."""
    base = datetime.now(timezone.utc) - timedelta(days=60)
    return [
        Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}",
            has_image=False,
            created_at=base + timedelta(seconds=i),
        )
        for i in range(count)
    ]


def _build_mocks(
    expired_convs: list[Conversation],
    messages_by_conv: dict[uuid.UUID, list[Message]],
    existing_summary_ids: set[uuid.UUID],
    summary_text: str,
) -> tuple[AsyncMock, AsyncMock]:
    """Build mock DB and Bedrock for run_expiry_job().

    Returns (mock_db, mock_bedrock).
    """
    mock_db = AsyncMock()
    mock_bedrock = AsyncMock(spec=BedrockService)
    mock_bedrock.generate_summary.return_value = summary_text
    mock_bedrock.generate_embedding.return_value = [0.1] * 1536

    # Track execute calls: first call returns expired conversations,
    # subsequent calls return either existing summary check or messages
    call_index = {"value": 0}

    async def execute_side_effect(stmt):
        idx = call_index["value"]
        call_index["value"] += 1

        result = MagicMock()

        if idx == 0:
            # First call: select expired conversations
            result.scalars.return_value.all.return_value = list(expired_convs)
            return result

        # Subsequent calls alternate between:
        # - checking for existing summary (scalar_one_or_none)
        # - fetching messages (scalars().all())
        # We need to figure out which based on the call pattern in run_expiry_job
        # The code does: select(SessionSummary.id) then select(Message)
        # For each conv: first a summary check, then optionally a message fetch

        # Use a simple approach: track per-conversation state
        return result

    # More precise mock: use side_effect list
    # For each expired conv, run_expiry_job does:
    #   1. execute(select(SessionSummary.id).where(...)) -> check existing summary
    #   2. If no summary: execute(select(Message).where(...)) -> get messages
    # Then delete(conv)

    execute_results = []

    # First call: select expired conversations
    expired_result = MagicMock()
    expired_result.scalars.return_value.all.return_value = list(expired_convs)
    execute_results.append(expired_result)

    for conv in expired_convs:
        # Summary existence check
        summary_check = MagicMock()
        if conv.id in existing_summary_ids:
            summary_check.scalar_one_or_none.return_value = uuid.uuid4()
        else:
            summary_check.scalar_one_or_none.return_value = None
        execute_results.append(summary_check)

        # If no existing summary, messages will be fetched
        if conv.id not in existing_summary_ids:
            msgs = messages_by_conv.get(conv.id, [])
            msg_result = MagicMock()
            msg_result.scalars.return_value.all.return_value = msgs
            execute_results.append(msg_result)

    mock_db.execute = AsyncMock(side_effect=execute_results)

    return mock_db, mock_bedrock


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestPropertyExpiryArchivalPreservesSummaries:
    """**Validates: Requirements 7.2, 7.3, 7.5**"""

    @given(
        days_past=days_past_expiry_st,
        msg_count=message_count_st,
        summary_text=summary_text_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_expiry_creates_summary_for_conversation_without_one(
        self,
        days_past: int,
        msg_count: int,
        summary_text: str,
    ) -> None:
        """For any expired conversation without an existing summary,
        run_expiry_job() SHALL create a session_summary record."""
        conv = _make_expired_conversation(days_past)
        messages = _make_messages(conv.id, msg_count)

        mock_db, mock_bedrock = _build_mocks(
            expired_convs=[conv],
            messages_by_conv={conv.id: messages},
            existing_summary_ids=set(),
            summary_text=summary_text,
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # A SessionSummary record MUST have been added
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, SessionSummary)
        assert added.conversation_id == conv.id
        assert added.summary_text == summary_text
        assert added.embedding == [0.1] * 1536

    @given(
        days_past=days_past_expiry_st,
        msg_count=message_count_st,
        summary_text=summary_text_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_expiry_deletes_conversation_after_archival(
        self,
        days_past: int,
        msg_count: int,
        summary_text: str,
    ) -> None:
        """For any expired conversation, run_expiry_job() SHALL delete the
        conversation itself (cascade removes messages/embeddings)."""
        conv = _make_expired_conversation(days_past)
        messages = _make_messages(conv.id, msg_count)

        mock_db, mock_bedrock = _build_mocks(
            expired_convs=[conv],
            messages_by_conv={conv.id: messages},
            existing_summary_ids=set(),
            summary_text=summary_text,
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # The conversation MUST have been deleted
        mock_db.delete.assert_awaited_once_with(conv)

    @given(days_past=days_past_expiry_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_expiry_skips_summary_generation_when_one_exists(
        self,
        days_past: int,
    ) -> None:
        """For any expired conversation that already has a session_summary,
        run_expiry_job() SHALL NOT generate a new summary but SHALL still
        delete the conversation."""
        conv = _make_expired_conversation(days_past)

        mock_db, mock_bedrock = _build_mocks(
            expired_convs=[conv],
            messages_by_conv={},
            existing_summary_ids={conv.id},
            summary_text="unused",
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # No new summary should be added (one already exists)
        mock_db.add.assert_not_called()

        # Bedrock should NOT be called for summary generation
        mock_bedrock.generate_summary.assert_not_called()

        # The conversation MUST still be deleted
        mock_db.delete.assert_awaited_once_with(conv)

    @given(
        days_past=days_past_expiry_st,
        msg_count=message_count_st,
        summary_text=summary_text_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_expiry_never_deletes_session_summaries(
        self,
        days_past: int,
        msg_count: int,
        summary_text: str,
    ) -> None:
        """run_expiry_job() SHALL NOT delete any records from the
        session_summaries table. Only conversations (and their cascaded
        messages/embeddings) are deleted."""
        conv = _make_expired_conversation(days_past)
        messages = _make_messages(conv.id, msg_count)

        mock_db, mock_bedrock = _build_mocks(
            expired_convs=[conv],
            messages_by_conv={conv.id: messages},
            existing_summary_ids=set(),
            summary_text=summary_text,
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)
        await manager.run_expiry_job()

        # Verify that delete was only called on the Conversation object,
        # never on a SessionSummary
        for delete_call in mock_db.delete.call_args_list:
            deleted_obj = delete_call[0][0]
            assert not isinstance(deleted_obj, SessionSummary), (
                "run_expiry_job() must NEVER delete SessionSummary records"
            )

        # Also verify no bulk delete was executed against session_summaries
        # by checking that execute() was never called with a delete statement
        # targeting session_summaries (the code uses db.delete(conv) not
        # db.execute(delete(...)))
        for exec_call in mock_db.execute.call_args_list:
            stmt = exec_call[0][0]
            stmt_str = str(stmt)
            assert "session_summaries" not in stmt_str.lower() or "DELETE" not in stmt_str.upper(), (
                "run_expiry_job() must not execute DELETE against session_summaries"
            )
