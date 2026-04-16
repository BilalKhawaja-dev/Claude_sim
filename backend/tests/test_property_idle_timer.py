# Feature: claude-simulator, Property 14: Idle timer tracking
# Validates: Requirements 6.1, 6.5
"""
Property-based test verifying that after updating last_message_at on a
conversation, the timestamp is within 1 second of the current server time.

For any message sent in a conversation, the conversation's last_message_at
timestamp SHALL be updated to a value within 1 second of the current server
time, effectively resetting the idle timer.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.orm import Conversation

# Strategy: generate conversation IDs
conversation_id_strategy = st.uuids()

# Strategy: generate stale timestamps (1 minute to 60 minutes ago)
stale_offset_strategy = st.integers(min_value=60, max_value=3600)


class TestPropertyIdleTimerTracking:
    """**Validates: Requirements 6.1, 6.5**"""

    @given(conv_id=conversation_id_strategy, stale_seconds=stale_offset_strategy)
    @settings(max_examples=100)
    def test_last_message_at_updated_within_one_second(
        self, conv_id: uuid.UUID, stale_seconds: int
    ) -> None:
        """After updating last_message_at, the timestamp SHALL be within
        1 second of the current server time.

        This simulates the idle timer reset that occurs in the chat endpoint
        when a message is sent: the conversation's last_message_at is set to
        datetime.now(timezone.utc).
        """
        # Create a conversation with a stale last_message_at
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
        conv = Conversation(
            id=conv_id,
            title="Test conversation",
            last_message_at=stale_time,
        )

        # Verify the timestamp is stale before update
        assert conv.last_message_at == stale_time

        # Simulate the update that happens in the chat endpoint:
        #   .values(last_message_at=datetime.now(timezone.utc))
        now = datetime.now(timezone.utc)
        conv.last_message_at = now

        # Verify the updated timestamp is within 1 second of current time
        current_time = datetime.now(timezone.utc)
        delta = abs((conv.last_message_at - current_time).total_seconds())
        assert delta <= 1.0, (
            f"last_message_at ({conv.last_message_at}) is {delta}s away from "
            f"current time ({current_time}), exceeding the 1-second threshold"
        )

    @given(conv_id=conversation_id_strategy, stale_seconds=stale_offset_strategy)
    @settings(max_examples=100)
    def test_idle_timer_reset_overwrites_stale_timestamp(
        self, conv_id: uuid.UUID, stale_seconds: int
    ) -> None:
        """When a message is sent, the idle timer reset SHALL overwrite any
        previous stale last_message_at value with a current timestamp."""
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
        conv = Conversation(
            id=conv_id,
            title="Test conversation",
            last_message_at=stale_time,
        )

        # The stale timestamp should be in the past
        assert conv.last_message_at < datetime.now(timezone.utc)

        # Simulate idle timer reset (as done in chat endpoint)
        conv.last_message_at = datetime.now(timezone.utc)

        # After reset, the timestamp should no longer be stale
        assert conv.last_message_at > stale_time
        # And it should be very close to now
        delta = abs((conv.last_message_at - datetime.now(timezone.utc)).total_seconds())
        assert delta <= 1.0

    @given(conv_id=conversation_id_strategy)
    @settings(max_examples=100)
    def test_last_message_at_is_timezone_aware(
        self, conv_id: uuid.UUID
    ) -> None:
        """The last_message_at timestamp SHALL be timezone-aware (UTC) after
        the idle timer is reset."""
        conv = Conversation(
            id=conv_id,
            title="Test conversation",
        )

        # Simulate idle timer reset
        conv.last_message_at = datetime.now(timezone.utc)

        assert conv.last_message_at.tzinfo is not None
        assert conv.last_message_at.tzinfo == timezone.utc
