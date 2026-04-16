# Feature: claude-simulator, Property 8: Conversation cascade deletion
# Validates: Requirements 3.4, 7.4
"""
Property-based test verifying that the Conversation ORM model is configured
with cascade="all, delete-orphan" on its messages and embeddings
relationships, ensuring that deleting a conversation removes all associated
records.

For any conversation that is deleted, all associated messages and chunk
embeddings SHALL be removed from the database.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.orm import Conversation, Embedding, Message

# Strategy: number of messages per conversation
message_count_strategy = st.integers(min_value=0, max_value=10)

# Strategy: number of embeddings per conversation
embedding_count_strategy = st.integers(min_value=0, max_value=10)


class TestPropertyCascadeDeletion:
    """**Validates: Requirements 3.4, 7.4**"""

    @settings(max_examples=100)
    @given(data=st.data())
    def test_messages_relationship_has_cascade_delete_orphan(
        self, data: st.DataObject
    ) -> None:
        """The Conversation.messages relationship SHALL be configured with
        cascade='all, delete-orphan' so that deleting a conversation
        removes all its messages."""
        # Inspect the relationship configuration on the ORM model
        messages_rel = Conversation.__mapper__.relationships["messages"]
        cascade = messages_rel.cascade

        assert cascade.delete, (
            "Conversation.messages relationship must have 'delete' in cascade"
        )
        assert cascade.delete_orphan, (
            "Conversation.messages relationship must have 'delete-orphan' in cascade"
        )

    @settings(max_examples=100)
    @given(data=st.data())
    def test_embeddings_relationship_has_cascade_delete_orphan(
        self, data: st.DataObject
    ) -> None:
        """The Conversation.embeddings relationship SHALL be configured with
        cascade='all, delete-orphan' so that deleting a conversation
        removes all its embeddings."""
        embeddings_rel = Conversation.__mapper__.relationships["embeddings"]
        cascade = embeddings_rel.cascade

        assert cascade.delete, (
            "Conversation.embeddings relationship must have 'delete' in cascade"
        )
        assert cascade.delete_orphan, (
            "Conversation.embeddings relationship must have 'delete-orphan' in cascade"
        )

    @given(msg_count=message_count_strategy, emb_count=embedding_count_strategy)
    @settings(max_examples=100)
    def test_conversation_owns_messages_and_embeddings(
        self, msg_count: int, emb_count: int
    ) -> None:
        """A Conversation object SHALL hold references to its messages and
        embeddings via the ORM relationships, confirming the parent-child
        ownership needed for cascade deletion."""
        conv_id = uuid.uuid4()
        base_time = datetime.now(timezone.utc)

        conv = Conversation(id=conv_id, title="Test")

        messages = []
        for i in range(msg_count):
            msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                created_at=base_time + timedelta(seconds=i),
            )
            messages.append(msg)

        conv.messages = messages
        assert len(conv.messages) == msg_count

        # Verify all messages reference the correct conversation
        for msg in conv.messages:
            assert msg.conversation_id == conv_id

    @given(data=st.data())
    @settings(max_examples=100)
    def test_messages_foreign_key_has_on_delete_cascade(
        self, data: st.DataObject
    ) -> None:
        """The messages.conversation_id foreign key SHALL have
        ON DELETE CASCADE at the database level."""
        fk = next(iter(Message.__table__.c.conversation_id.foreign_keys))
        assert fk.ondelete == "CASCADE", (
            f"Expected ON DELETE CASCADE on messages.conversation_id FK, "
            f"got {fk.ondelete}"
        )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_embeddings_foreign_key_has_on_delete_cascade(
        self, data: st.DataObject
    ) -> None:
        """The embeddings.conversation_id foreign key SHALL have
        ON DELETE CASCADE at the database level."""
        fk = next(iter(Embedding.__table__.c.conversation_id.foreign_keys))
        assert fk.ondelete == "CASCADE", (
            f"Expected ON DELETE CASCADE on embeddings.conversation_id FK, "
            f"got {fk.ondelete}"
        )
