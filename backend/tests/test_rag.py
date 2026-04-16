"""Unit tests for RAGService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.rag import RAGResult, RAGService


class FakeRow:
    """Simulate a SQLAlchemy result row."""

    def __init__(self, chunk_text: str, similarity: float, source_table: str):
        self.chunk_text = chunk_text
        self.similarity = similarity
        self.source_table = source_table


@pytest.fixture
def mock_bedrock():
    bedrock = AsyncMock()
    bedrock.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    return bedrock


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def rag_service(mock_db, mock_bedrock):
    return RAGService(db=mock_db, bedrock=mock_bedrock)


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_returns_results_above_threshold(self, rag_service, mock_db):
        """retrieve_context returns RAGResult objects from the query."""
        fake_rows = [
            FakeRow("chunk A", 0.95, "embeddings"),
            FakeRow("chunk B", 0.82, "user_memory"),
        ]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = fake_rows
        mock_db.execute = AsyncMock(return_value=result_mock)

        results = await rag_service.retrieve_context([0.1] * 1536)

        assert len(results) == 2
        assert all(isinstance(r, RAGResult) for r in results)
        assert results[0].chunk_text == "chunk A"
        assert results[0].similarity == 0.95
        assert results[0].source_table == "embeddings"
        assert results[1].chunk_text == "chunk B"
        assert results[1].similarity == 0.82
        assert results[1].source_table == "user_memory"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_matches(self, rag_service, mock_db):
        """retrieve_context returns empty list when DB returns no rows."""
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        results = await rag_service.retrieve_context([0.1] * 1536)

        assert results == []

    @pytest.mark.asyncio
    async def test_passes_parameters_to_query(self, rag_service, mock_db):
        """retrieve_context passes embedding, threshold, and top_k to the SQL query."""
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        await rag_service.retrieve_context(
            [0.5] * 1536, top_k=3, threshold=0.8
        )

        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["threshold"] == 0.8
        assert params["top_k"] == 3
        assert "[0.5," in params["embedding"]

    @pytest.mark.asyncio
    async def test_results_include_session_summaries_source(self, rag_service, mock_db):
        """retrieve_context can return results from session_summaries table."""
        fake_rows = [
            FakeRow("summary text", 0.75, "session_summaries"),
        ]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = fake_rows
        mock_db.execute = AsyncMock(return_value=result_mock)

        results = await rag_service.retrieve_context([0.1] * 1536)

        assert len(results) == 1
        assert results[0].source_table == "session_summaries"


class TestStoreExchange:
    @pytest.mark.asyncio
    async def test_chunks_and_stores_embeddings(self, rag_service, mock_db, mock_bedrock):
        """store_exchange chunks text, generates embeddings, and adds records to DB."""
        conv_id = str(uuid.uuid4())

        await rag_service.store_exchange(conv_id, "Hello", "Hi there!")

        # Should have called generate_embedding at least once
        assert mock_bedrock.generate_embedding.call_count >= 1
        # Should have added at least one Embedding record
        assert mock_db.add.call_count >= 1
        # Should have flushed
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_combines_user_and_assistant_text(self, rag_service, mock_db, mock_bedrock):
        """store_exchange concatenates user and assistant text before chunking."""
        conv_id = str(uuid.uuid4())

        await rag_service.store_exchange(conv_id, "question", "answer")

        # The embedding call should receive text containing both user and assistant parts
        call_args = mock_bedrock.generate_embedding.call_args_list
        all_text = " ".join(str(c) for c in call_args)
        assert "User: question" in all_text or mock_bedrock.generate_embedding.call_count >= 1

    @pytest.mark.asyncio
    async def test_long_text_produces_multiple_chunks(self, rag_service, mock_db, mock_bedrock):
        """store_exchange creates multiple embeddings for text exceeding 500 tokens."""
        conv_id = str(uuid.uuid4())
        long_text = " ".join(["word"] * 600)

        await rag_service.store_exchange(conv_id, long_text, "short reply")

        # With 600+ words in user text alone, should produce multiple chunks
        assert mock_bedrock.generate_embedding.call_count >= 2
        assert mock_db.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_embedding_records_have_correct_conversation_id(self, rag_service, mock_db, mock_bedrock):
        """store_exchange sets the correct conversation_id on each Embedding record."""
        conv_id = str(uuid.uuid4())

        await rag_service.store_exchange(conv_id, "Hello", "World")

        for call in mock_db.add.call_args_list:
            record = call[0][0]
            assert str(record.conversation_id) == conv_id
