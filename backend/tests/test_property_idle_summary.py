# Feature: claude-simulator, Property 15: Idle summary generation trigger
# Validates: Requirements 6.2
"""
Property-based test verifying that check_idle_conversations() correctly
identifies conversations that have been idle for >= 5 minutes and does NOT
identify conversations that have been idle for < 5 minutes.

For any conversation where the elapsed time since last_message_at is >= 5
minutes, the Session_Manager's idle check SHALL identify that conversation
as requiring a summary.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import settings as app_settings
from app.models.orm import Conversation
from app.services.bedrock import BedrockService
from app.services.session import SessionManager

# Strategy: idle durations at or above the 5-minute threshold (in seconds)
idle_seconds_at_or_above = st.integers(
    min_value=app_settings.idle_timeout_minutes * 60,
    max_value=24 * 60 * 60,  # up to 1 day
)

# Strategy: idle durations strictly below the 5-minute threshold (in seconds)
idle_seconds_below = st.integers(
    min_value=0,
    max_value=app_settings.idle_timeout_minutes * 60 - 1,
)


def _build_session_manager_with_conversations(
    conversations: list[Conversation],
) -> SessionManager:
    """Build a SessionManager with a mocked DB that returns the given conversations
    filtered by the idle threshold, matching the real query logic."""
    mock_db = AsyncMock()
    mock_bedrock = AsyncMock(spec=BedrockService)

    threshold = datetime.now(timezone.utc) - timedelta(
        minutes=app_settings.idle_timeout_minutes
    )

    # Simulate the DB query: return IDs where last_message_at <= threshold
    idle_ids = [
        conv.id for conv in conversations if conv.last_message_at <= threshold
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = idle_ids
    mock_db.execute.return_value = mock_result

    return SessionManager(db=mock_db, bedrock=mock_bedrock)


class TestPropertyIdleSummaryGenerationTrigger:
    """**Validates: Requirements 6.2**"""

    @given(idle_seconds=idle_seconds_at_or_above)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_idle_conversations_identified_when_at_or_above_threshold(
        self, idle_seconds: int
    ) -> None:
        """Conversations idle for >= 5 minutes SHALL be identified as requiring
        a summary by check_idle_conversations()."""
        conv_id = uuid.uuid4()
        last_msg_time = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
        conv = Conversation(
            id=conv_id,
            title="Idle conversation",
            last_message_at=last_msg_time,
        )

        manager = _build_session_manager_with_conversations([conv])
        result = await manager.check_idle_conversations()

        assert str(conv_id) in result, (
            f"Conversation idle for {idle_seconds}s (>= {app_settings.idle_timeout_minutes * 60}s) "
            f"was NOT identified as idle"
        )

    @given(idle_seconds=idle_seconds_below)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_active_conversations_not_identified_when_below_threshold(
        self, idle_seconds: int
    ) -> None:
        """Conversations idle for < 5 minutes SHALL NOT be identified as
        requiring a summary by check_idle_conversations()."""
        conv_id = uuid.uuid4()
        last_msg_time = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
        conv = Conversation(
            id=conv_id,
            title="Active conversation",
            last_message_at=last_msg_time,
        )

        manager = _build_session_manager_with_conversations([conv])
        result = await manager.check_idle_conversations()

        assert str(conv_id) not in result, (
            f"Conversation idle for {idle_seconds}s (< {app_settings.idle_timeout_minutes * 60}s) "
            f"was incorrectly identified as idle"
        )

    @given(
        idle_seconds=idle_seconds_at_or_above,
        active_seconds=idle_seconds_below,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_mixed_conversations_correctly_partitioned(
        self, idle_seconds: int, active_seconds: int
    ) -> None:
        """When both idle and active conversations exist, only the idle ones
        (>= 5 min) SHALL be identified."""
        idle_id = uuid.uuid4()
        active_id = uuid.uuid4()

        idle_conv = Conversation(
            id=idle_id,
            title="Idle",
            last_message_at=datetime.now(timezone.utc) - timedelta(seconds=idle_seconds),
        )
        active_conv = Conversation(
            id=active_id,
            title="Active",
            last_message_at=datetime.now(timezone.utc) - timedelta(seconds=active_seconds),
        )

        manager = _build_session_manager_with_conversations([idle_conv, active_conv])
        result = await manager.check_idle_conversations()

        assert str(idle_id) in result, "Idle conversation should be identified"
        assert str(active_id) not in result, "Active conversation should NOT be identified"
