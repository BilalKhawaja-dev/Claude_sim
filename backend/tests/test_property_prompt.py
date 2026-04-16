# Feature: claude-simulator, Property 1: Prompt includes conversation history and RAG context
# Validates: Requirements 1.1, 4.3, 4.6
"""
Property-based tests verifying that:
1. _build_system_prompt always includes the base prompt text.
2. When RAG results are provided, all chunk texts appear in the system prompt.
3. When no RAG results, the prompt still contains the base prompt without RAG context.
4. _build_history_messages returns messages in chronological order matching input.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.api.chat import _build_history_messages, _build_system_prompt
from app.services.rag import RAGResult


# --- Constants ---

BASE_PROMPT_FRAGMENT = "You are Claude, an AI assistant made by Anthropic"

# --- Strategies ---

rag_result_strategy = st.builds(
    RAGResult,
    chunk_text=st.text(min_size=1, max_size=200).filter(lambda t: t.strip()),
    similarity=st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
    source_table=st.sampled_from(["embeddings", "user_memory", "session_summaries"]),
)

rag_result_list_strategy = st.lists(rag_result_strategy, min_size=1, max_size=10)

ROLES = ["user", "assistant"]

message_pair_strategy = st.tuples(
    st.text(min_size=1, max_size=200),
    st.text(min_size=1, max_size=200),
)


def _make_mock_db(messages: list) -> AsyncMock:
    """Create a mocked async DB session that returns the given Message list."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages
    mock_db.execute.return_value = mock_result
    return mock_db


class TestPropertyBuildSystemPrompt:
    """Property 1: Prompt includes conversation history and RAG context — system prompt tests."""

    @settings(max_examples=100)
    @given(rag_chunks=rag_result_list_strategy)
    def test_base_prompt_always_present_with_rag(self, rag_chunks: list[RAGResult]) -> None:
        """**Validates: Requirements 1.1**

        _build_system_prompt always includes the base prompt text,
        regardless of whether RAG results are provided.
        """
        prompt = _build_system_prompt(rag_chunks)
        assert BASE_PROMPT_FRAGMENT in prompt

    @settings(max_examples=100)
    @given(data=st.data())
    def test_base_prompt_present_without_rag(self, data: st.DataObject) -> None:
        """**Validates: Requirements 4.6**

        When no RAG results are available, the prompt still contains
        the base prompt without RAG context.
        """
        prompt = _build_system_prompt([])
        assert BASE_PROMPT_FRAGMENT in prompt
        # Should NOT contain the RAG context header
        assert "retrieved from memory" not in prompt

    @settings(max_examples=100)
    @given(rag_chunks=rag_result_list_strategy)
    def test_all_rag_chunks_appear_in_prompt(self, rag_chunks: list[RAGResult]) -> None:
        """**Validates: Requirements 4.3**

        When RAG results are provided, every chunk_text appears in the
        system prompt so the LLM can use the retrieved context.
        """
        prompt = _build_system_prompt(rag_chunks)
        for chunk in rag_chunks:
            assert chunk.chunk_text in prompt, (
                f"RAG chunk text '{chunk.chunk_text}' not found in system prompt"
            )

    @settings(max_examples=100)
    @given(rag_chunks=rag_result_list_strategy)
    def test_rag_context_header_present_when_chunks_provided(
        self, rag_chunks: list[RAGResult]
    ) -> None:
        """**Validates: Requirements 4.3**

        When RAG results are provided, the prompt includes the context
        header indicating retrieved memory is present.
        """
        prompt = _build_system_prompt(rag_chunks)
        assert "retrieved from memory" in prompt


class TestPropertyBuildHistoryMessages:
    """Property 1: Prompt includes conversation history and RAG context — history tests."""

    @settings(max_examples=100)
    @given(
        pairs=st.lists(message_pair_strategy, min_size=1, max_size=10),
    )
    @pytest.mark.asyncio
    async def test_history_messages_chronological_order(
        self, pairs: list[tuple[str, str]]
    ) -> None:
        """**Validates: Requirements 1.1**

        _build_history_messages returns messages in chronological order
        matching the input order. Each user/assistant pair preserves
        its position in the conversation timeline.
        """
        conv_id = uuid.uuid4()
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        messages = []

        for i, (user_text, assistant_text) in enumerate(pairs):
            user_msg = MagicMock(spec=["role", "content", "has_image", "image_data", "created_at"])
            user_msg.role = "user"
            user_msg.content = user_text
            user_msg.has_image = False
            user_msg.image_data = None
            user_msg.created_at = base_time + timedelta(minutes=i * 2)
            messages.append(user_msg)

            asst_msg = MagicMock(spec=["role", "content", "has_image", "image_data", "created_at"])
            asst_msg.role = "assistant"
            asst_msg.content = assistant_text
            asst_msg.has_image = False
            asst_msg.image_data = None
            asst_msg.created_at = base_time + timedelta(minutes=i * 2 + 1)
            messages.append(asst_msg)

        mock_db = _make_mock_db(messages)
        history = await _build_history_messages(mock_db, conv_id)

        # Verify count matches
        assert len(history) == len(messages)

        # Verify chronological order: roles alternate user/assistant
        for i, (user_text, assistant_text) in enumerate(pairs):
            assert history[i * 2]["role"] == "user"
            assert history[i * 2]["content"] == user_text
            assert history[i * 2 + 1]["role"] == "assistant"
            assert history[i * 2 + 1]["content"] == assistant_text
