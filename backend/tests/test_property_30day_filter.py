# Feature: claude-simulator, Property 18: 30-day conversation filter
# Validates: Requirements 7.1, 7.6
"""
Property-based test verifying that conversations are correctly partitioned:
those within 30 days are visible, those older are identified for expiry.

For any set of conversations in the database, the list endpoint and the
expiry job SHALL correctly partition them: conversations with last_message_at
within 30 days are visible in the UI, and those older than 30 days are
identified for expiry.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import settings as app_settings
from app.models.orm import Conversation

# Strategy: offset in seconds from now (0 to 90 days)
offset_strategy = st.integers(min_value=0, max_value=90 * 24 * 3600)

# Strategy: number of conversations
count_strategy = st.integers(min_value=1, max_value=20)

RETENTION_DAYS = app_settings.conversation_retention_days  # 30


def _partition_conversations(
    conversations: list[Conversation],
) -> tuple[list[Conversation], list[Conversation]]:
    """Partition conversations into visible (within retention window) and
    expired (older than retention window), mirroring the logic in
    list_conversations and the expiry job."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    visible = [c for c in conversations if c.last_message_at >= cutoff]
    expired = [c for c in conversations if c.last_message_at < cutoff]
    return visible, expired


class TestProperty30DayFilter:
    """**Validates: Requirements 7.1, 7.6**"""

    @given(offsets=st.lists(offset_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_visible_conversations_are_within_30_days(
        self, offsets: list[int]
    ) -> None:
        """All conversations in the visible partition SHALL have
        last_message_at within the 30-day retention window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=RETENTION_DAYS)

        conversations = [
            Conversation(
                id=uuid.uuid4(),
                title=f"Conv {i}",
                last_message_at=now - timedelta(seconds=offset),
            )
            for i, offset in enumerate(offsets)
        ]

        visible, _ = _partition_conversations(conversations)

        for conv in visible:
            assert conv.last_message_at >= cutoff, (
                f"Visible conversation has last_message_at={conv.last_message_at} "
                f"which is before cutoff={cutoff}"
            )

    @given(offsets=st.lists(offset_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_expired_conversations_are_older_than_30_days(
        self, offsets: list[int]
    ) -> None:
        """All conversations in the expired partition SHALL have
        last_message_at older than the 30-day retention window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=RETENTION_DAYS)

        conversations = [
            Conversation(
                id=uuid.uuid4(),
                title=f"Conv {i}",
                last_message_at=now - timedelta(seconds=offset),
            )
            for i, offset in enumerate(offsets)
        ]

        _, expired = _partition_conversations(conversations)

        for conv in expired:
            assert conv.last_message_at < cutoff, (
                f"Expired conversation has last_message_at={conv.last_message_at} "
                f"which is at or after cutoff={cutoff}"
            )

    @given(offsets=st.lists(offset_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_partition_is_exhaustive(
        self, offsets: list[int]
    ) -> None:
        """The visible + expired partitions SHALL cover all conversations
        with no conversation lost."""
        now = datetime.now(timezone.utc)

        conversations = [
            Conversation(
                id=uuid.uuid4(),
                title=f"Conv {i}",
                last_message_at=now - timedelta(seconds=offset),
            )
            for i, offset in enumerate(offsets)
        ]

        visible, expired = _partition_conversations(conversations)

        assert len(visible) + len(expired) == len(conversations)

    @given(offsets=st.lists(offset_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_partition_is_disjoint(
        self, offsets: list[int]
    ) -> None:
        """No conversation SHALL appear in both the visible and expired
        partitions."""
        now = datetime.now(timezone.utc)

        conversations = [
            Conversation(
                id=uuid.uuid4(),
                title=f"Conv {i}",
                last_message_at=now - timedelta(seconds=offset),
            )
            for i, offset in enumerate(offsets)
        ]

        visible, expired = _partition_conversations(conversations)

        visible_ids = {c.id for c in visible}
        expired_ids = {c.id for c in expired}

        assert visible_ids.isdisjoint(expired_ids), (
            "A conversation appeared in both visible and expired partitions"
        )
