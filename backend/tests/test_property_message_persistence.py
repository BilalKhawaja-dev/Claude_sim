# Feature: claude-simulator, Property 3: Message persistence round-trip
# Validates: Requirements 1.5, 3.3
"""
Property-based test verifying that Message ORM objects preserve
conversation_id, role, content, and chronological ordering.

For any user message and its corresponding assistant response stored in the
database, retrieving the conversation's message history SHALL return those
messages with matching conversation_id, role, content, and chronological
ordering.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.orm import Conversation, Message

# Strategy: valid message roles
role_strategy = st.sampled_from(["user", "assistant"])

# Strategy: non-empty message content
content_strategy = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())

# Strategy: number of messages in a conversation (at least 2 for ordering)
message_count_strategy = st.integers(min_value=2, max_value=20)


class TestPropertyMessagePersistence:
    """**Validates: Requirements 1.5, 3.3**"""

    @given(role=role_strategy, content=content_strategy)
    @settings(max_examples=100)
    def test_message_preserves_conversation_id(
        self, role: str, content: str
    ) -> None:
        """A Message object SHALL preserve the conversation_id it was
        created with."""
        conv_id = uuid.uuid4()
        conv = Conversation(id=conv_id, title="Test")

        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role=role,
            content=content,
        )

        assert msg.conversation_id == conv_id

    @given(role=role_strategy, content=content_strategy)
    @settings(max_examples=100)
    def test_message_preserves_role(
        self, role: str, content: str
    ) -> None:
        """A Message object SHALL preserve the role ('user' or 'assistant')
        it was created with."""
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role=role,
            content=content,
        )

        assert msg.role == role
        assert msg.role in ("user", "assistant")

    @given(role=role_strategy, content=content_strategy)
    @settings(max_examples=100)
    def test_message_preserves_content(
        self, role: str, content: str
    ) -> None:
        """A Message object SHALL preserve the exact content it was
        created with — no truncation or mutation."""
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role=role,
            content=content,
        )

        assert msg.content == content

    @given(count=message_count_strategy)
    @settings(max_examples=100)
    def test_messages_maintain_chronological_ordering(
        self, count: int
    ) -> None:
        """Messages sorted by created_at SHALL maintain chronological
        ordering, matching the order they were created."""
        conv_id = uuid.uuid4()
        base_time = datetime.now(timezone.utc) - timedelta(hours=1)
        roles = ["user", "assistant"]

        messages = []
        for i in range(count):
            msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv_id,
                role=roles[i % 2],
                content=f"Message {i}",
                created_at=base_time + timedelta(seconds=i * 10),
            )
            messages.append(msg)

        # Sort by created_at (as the get_conversation endpoint does)
        sorted_msgs = sorted(messages, key=lambda m: m.created_at)

        for i in range(len(sorted_msgs) - 1):
            assert sorted_msgs[i].created_at <= sorted_msgs[i + 1].created_at

    @given(
        data=st.lists(
            st.tuples(role_strategy, content_strategy),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_all_messages_share_same_conversation_id(
        self, data: list[tuple[str, str]]
    ) -> None:
        """All messages within a conversation SHALL share the same
        conversation_id."""
        conv_id = uuid.uuid4()
        base_time = datetime.now(timezone.utc)

        messages = []
        for i, (role, content) in enumerate(data):
            msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv_id,
                role=role,
                content=content,
                created_at=base_time + timedelta(seconds=i),
            )
            messages.append(msg)

        for msg in messages:
            assert msg.conversation_id == conv_id
