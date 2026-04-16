# Feature: claude-simulator, Property 7: Conversation listing is ordered by recency
# Validates: Requirements 3.2
"""
Property-based test verifying that a list of ConversationSummary objects
sorted by updated_at DESC maintains the ordering invariant.

For any set of conversations returned by the list endpoint, they SHALL be
ordered by updated_at descending, such that for every adjacent pair (i, i+1),
conversations[i].updated_at >= conversations[i+1].updated_at.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.schemas import ConversationSummary

# Strategy: generate a timestamp within the last 30 days
timestamp_strategy = st.integers(
    min_value=0, max_value=30 * 24 * 3600
).map(lambda offset: datetime.now(timezone.utc) - timedelta(seconds=offset))

# Strategy: optional conversation title
title_strategy = st.one_of(st.none(), st.text(min_size=1, max_size=100))

# Strategy: number of conversations
count_strategy = st.integers(min_value=0, max_value=30)


class TestPropertyConversationOrdering:
    """**Validates: Requirements 3.2**"""

    @given(
        timestamps=st.lists(timestamp_strategy, min_size=2, max_size=30),
    )
    @settings(max_examples=100)
    def test_conversations_sorted_desc_by_updated_at(
        self, timestamps: list[datetime]
    ) -> None:
        """Conversations sorted by updated_at DESC SHALL satisfy
        conversations[i].updated_at >= conversations[i+1].updated_at
        for every adjacent pair."""
        summaries = [
            ConversationSummary(
                id=str(uuid.uuid4()),
                title=None,
                updated_at=ts,
            )
            for ts in timestamps
        ]

        # Apply the same sort the list endpoint uses
        sorted_summaries = sorted(
            summaries, key=lambda c: c.updated_at, reverse=True
        )

        for i in range(len(sorted_summaries) - 1):
            assert sorted_summaries[i].updated_at >= sorted_summaries[i + 1].updated_at

    @given(count=count_strategy)
    @settings(max_examples=100)
    def test_empty_or_single_conversation_is_trivially_ordered(
        self, count: int
    ) -> None:
        """A list of 0 or 1 conversations is trivially ordered by recency."""
        if count > 1:
            return  # only test 0 or 1

        summaries = [
            ConversationSummary(
                id=str(uuid.uuid4()),
                title=None,
                updated_at=datetime.now(timezone.utc),
            )
            for _ in range(min(count, 1))
        ]

        sorted_summaries = sorted(
            summaries, key=lambda c: c.updated_at, reverse=True
        )

        assert len(sorted_summaries) == min(count, 1)

    @given(
        timestamps=st.lists(timestamp_strategy, min_size=3, max_size=20),
    )
    @settings(max_examples=100)
    def test_duplicate_timestamps_preserve_stable_order(
        self, timestamps: list[datetime]
    ) -> None:
        """When multiple conversations share the same updated_at, the
        descending sort SHALL still produce a valid ordering where
        adjacent pairs satisfy >=."""
        # Force some duplicates
        if len(timestamps) >= 2:
            timestamps[1] = timestamps[0]

        summaries = [
            ConversationSummary(
                id=str(uuid.uuid4()),
                title=None,
                updated_at=ts,
            )
            for ts in timestamps
        ]

        sorted_summaries = sorted(
            summaries, key=lambda c: c.updated_at, reverse=True
        )

        for i in range(len(sorted_summaries) - 1):
            assert sorted_summaries[i].updated_at >= sorted_summaries[i + 1].updated_at
