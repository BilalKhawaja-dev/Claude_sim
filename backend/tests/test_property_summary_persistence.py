# Feature: claude-simulator, Property 17: Summary persistence regardless of email outcome
# Validates: Requirements 6.6
"""
Property-based test verifying that generate_and_email_summary() always stores
the summary text and its embedding in the session_summaries table regardless
of whether the email send succeeds, fails with an exception, or fails due to
an ImportError (EmailService not available).

For any generated session summary, the summary text and its embedding SHALL be
stored in the session_summaries table regardless of whether the email send
succeeds or fails.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.orm import Conversation, Message, SessionSummary
from app.services.bedrock import BedrockService
from app.services.session import SessionManager

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate non-empty summary text (simulates Bedrock output)
summary_text_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=500,
).filter(lambda s: s.strip())

# Generate non-empty conversation titles
title_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Generate non-empty message content
message_content_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())

# Email outcome: one of success, exception, or import error
email_outcome_st = st.sampled_from(["success", "exception", "import_error"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mocks(
    conv_title: str,
    message_content: str,
    summary_text: str,
    email_outcome: str,
) -> tuple[AsyncMock, AsyncMock, Conversation]:
    """Build mock DB and Bedrock, returning (mock_db, mock_bedrock, conversation)."""
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        title=conv_title,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
    )

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="user",
        content=message_content,
        has_image=False,
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.get.return_value = conv

    msg_result = MagicMock()
    msg_result.scalars.return_value.all.return_value = [msg]
    mock_db.execute.return_value = msg_result

    mock_bedrock = AsyncMock(spec=BedrockService)
    mock_bedrock.generate_summary.return_value = summary_text
    mock_bedrock.generate_embedding.return_value = [0.1] * 1536

    return mock_db, mock_bedrock, conv


def _patch_email(email_outcome: str):
    """Return a context manager that patches the email import according to outcome."""
    if email_outcome == "success":
        mock_email_cls = MagicMock()
        mock_email_instance = AsyncMock()
        mock_email_cls.return_value = mock_email_instance
        mock_module = MagicMock()
        mock_module.EmailService = mock_email_cls
        return patch.dict("sys.modules", {"app.services.email": mock_module})

    elif email_outcome == "exception":
        mock_email_cls = MagicMock()
        mock_email_instance = AsyncMock()
        mock_email_instance.send_session_summary.side_effect = Exception("SES send failed")
        mock_email_cls.return_value = mock_email_instance
        mock_module = MagicMock()
        mock_module.EmailService = mock_email_cls
        return patch.dict("sys.modules", {"app.services.email": mock_module})

    else:  # import_error — remove the module so the import inside the method raises ImportError
        return patch.dict("sys.modules", {"app.services.email": None})


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestPropertySummaryPersistenceRegardlessOfEmailOutcome:
    """**Validates: Requirements 6.6**"""

    @given(
        summary_text=summary_text_st,
        conv_title=title_st,
        message_content=message_content_st,
        email_outcome=email_outcome_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_summary_stored_regardless_of_email_outcome(
        self,
        summary_text: str,
        conv_title: str,
        message_content: str,
        email_outcome: str,
    ) -> None:
        """For any generated session summary, the summary text and its embedding
        SHALL be stored in the session_summaries table regardless of whether the
        email send succeeds or fails."""
        mock_db, mock_bedrock, conv = _build_mocks(
            conv_title, message_content, summary_text, email_outcome,
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        with _patch_email(email_outcome):
            await manager.generate_and_email_summary(str(conv.id))

        # The summary record MUST have been added to the DB session
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert isinstance(added_record, SessionSummary)
        assert added_record.summary_text == summary_text
        assert added_record.conversation_id == conv.id
        assert added_record.embedding == [0.1] * 1536

        # The DB session MUST have been committed
        mock_db.commit.assert_awaited_once()

    @given(
        summary_text=summary_text_st,
        message_content=message_content_st,
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_summary_stored_when_email_succeeds(
        self,
        summary_text: str,
        message_content: str,
    ) -> None:
        """Focused check: summary persisted when email send succeeds."""
        mock_db, mock_bedrock, conv = _build_mocks(
            "Chat", message_content, summary_text, "success",
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        with _patch_email("success"):
            await manager.generate_and_email_summary(str(conv.id))

        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert isinstance(added_record, SessionSummary)
        assert added_record.summary_text == summary_text
        mock_db.commit.assert_awaited_once()

    @given(
        summary_text=summary_text_st,
        message_content=message_content_st,
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_summary_stored_when_email_fails_with_exception(
        self,
        summary_text: str,
        message_content: str,
    ) -> None:
        """Focused check: summary persisted when email send raises an exception."""
        mock_db, mock_bedrock, conv = _build_mocks(
            "Chat", message_content, summary_text, "exception",
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        with _patch_email("exception"):
            await manager.generate_and_email_summary(str(conv.id))

        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert isinstance(added_record, SessionSummary)
        assert added_record.summary_text == summary_text
        mock_db.commit.assert_awaited_once()

    @given(
        summary_text=summary_text_st,
        message_content=message_content_st,
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_summary_stored_when_email_import_fails(
        self,
        summary_text: str,
        message_content: str,
    ) -> None:
        """Focused check: summary persisted when EmailService import raises ImportError."""
        mock_db, mock_bedrock, conv = _build_mocks(
            "Chat", message_content, summary_text, "import_error",
        )

        manager = SessionManager(db=mock_db, bedrock=mock_bedrock)

        with _patch_email("import_error"):
            await manager.generate_and_email_summary(str(conv.id))

        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert isinstance(added_record, SessionSummary)
        assert added_record.summary_text == summary_text
        mock_db.commit.assert_awaited_once()
