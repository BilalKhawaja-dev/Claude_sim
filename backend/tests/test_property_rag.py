# Feature: claude-simulator, Property 10: RAG retrieval constraints
# Validates: Requirements 4.2, 4.5, 5.5
"""
Property-based test verifying that the RAG engine returns at most top_k results,
all with cosine similarity >= threshold, ordered by similarity descending,
and that results can come from all three source tables (embeddings, user_memory,
session_summaries).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.rag import RAGResult, RAGService


# --- Strategies ---

SOURCE_TABLES = ["embeddings", "user_memory", "session_summaries"]

rag_result_strategy = st.builds(
    lambda text, sim, table: MagicMock(
        chunk_text=text, similarity=sim, source_table=table
    ),
    text=st.text(min_size=1, max_size=200),
    sim=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    table=st.sampled_from(SOURCE_TABLES),
)

rag_result_list_strategy = st.lists(rag_result_strategy, min_size=0, max_size=20)


def _make_rag_service(fake_rows: list) -> RAGService:
    """Create a RAGService with a mocked DB that returns the given rows."""
    mock_db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = fake_rows
    mock_db.execute = AsyncMock(return_value=result_mock)

    mock_bedrock = AsyncMock()
    return RAGService(db=mock_db, bedrock=mock_bedrock)


class TestRAGRetrievalConstraints:
    """Property 10: RAG retrieval constraints."""

    @settings(max_examples=100)
    @given(
        rows=rag_result_list_strategy,
        top_k=st.integers(min_value=1, max_value=10),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @pytest.mark.asyncio
    async def test_result_count_at_most_top_k(
        self, rows: list, top_k: int, threshold: float
    ) -> None:
        """**Validates: Requirements 4.2**

        For any query embedding, the RAG_Engine SHALL return at most top_k results.

        We simulate the DB returning pre-filtered rows (as the SQL query does
        the filtering), and verify retrieve_context never returns more than top_k.
        """
        # The SQL query handles filtering/limiting, so we simulate the DB
        # returning at most top_k rows that pass the threshold.
        filtered = [r for r in rows if r.similarity >= threshold]
        filtered.sort(key=lambda r: r.similarity, reverse=True)
        db_rows = filtered[:top_k]

        service = _make_rag_service(db_rows)
        results = await service.retrieve_context(
            [0.1] * 1536, top_k=top_k, threshold=threshold
        )

        assert len(results) <= top_k

    @settings(max_examples=100)
    @given(
        rows=rag_result_list_strategy,
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @pytest.mark.asyncio
    async def test_all_results_above_threshold(
        self, rows: list, threshold: float
    ) -> None:
        """**Validates: Requirements 4.5**

        For any query embedding, all returned results SHALL have
        cosine similarity >= threshold.
        """
        # Simulate DB returning only rows above threshold (as the SQL WHERE does)
        db_rows = [r for r in rows if r.similarity >= threshold][:5]

        service = _make_rag_service(db_rows)
        results = await service.retrieve_context(
            [0.1] * 1536, top_k=5, threshold=threshold
        )

        for result in results:
            assert result.similarity >= threshold, (
                f"Result similarity {result.similarity} < threshold {threshold}"
            )

    @settings(max_examples=100)
    @given(rows=rag_result_list_strategy)
    @pytest.mark.asyncio
    async def test_results_ordered_by_similarity_descending(
        self, rows: list
    ) -> None:
        """**Validates: Requirements 4.2, 4.5**

        For any query embedding, results SHALL be ordered by similarity descending.
        """
        # Simulate DB returning rows sorted descending (as the SQL ORDER BY does)
        filtered = [r for r in rows if r.similarity >= 0.7]
        filtered.sort(key=lambda r: r.similarity, reverse=True)
        db_rows = filtered[:5]

        service = _make_rag_service(db_rows)
        results = await service.retrieve_context([0.1] * 1536)

        for i in range(len(results) - 1):
            assert results[i].similarity >= results[i + 1].similarity, (
                f"Results not sorted: {results[i].similarity} < {results[i+1].similarity}"
            )

    @settings(max_examples=100)
    @given(
        emb_rows=st.lists(
            st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0, max_size=3,
        ),
        mem_rows=st.lists(
            st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0, max_size=3,
        ),
        sum_rows=st.lists(
            st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0, max_size=3,
        ),
    )
    @pytest.mark.asyncio
    async def test_results_span_all_three_tables(
        self, emb_rows: list, mem_rows: list, sum_rows: list
    ) -> None:
        """**Validates: Requirements 4.2, 5.5**

        Results can come from all three source tables: embeddings,
        user_memory, and session_summaries.
        """
        # Build fake rows from each table
        all_rows = []
        for sim in emb_rows:
            row = MagicMock(chunk_text="emb chunk", similarity=sim, source_table="embeddings")
            all_rows.append(row)
        for sim in mem_rows:
            row = MagicMock(chunk_text="mem chunk", similarity=sim, source_table="user_memory")
            all_rows.append(row)
        for sim in sum_rows:
            row = MagicMock(chunk_text="sum chunk", similarity=sim, source_table="session_summaries")
            all_rows.append(row)

        # Sort descending and limit to 5 (simulating DB behavior)
        all_rows.sort(key=lambda r: r.similarity, reverse=True)
        db_rows = all_rows[:5]

        service = _make_rag_service(db_rows)
        results = await service.retrieve_context([0.1] * 1536)

        # Verify results come from the expected tables
        result_tables = {r.source_table for r in results}
        expected_tables = set()
        for row in db_rows:
            expected_tables.add(row.source_table)

        assert result_tables == expected_tables, (
            f"Expected tables {expected_tables}, got {result_tables}"
        )

        # All returned source_tables must be valid
        for r in results:
            assert r.source_table in {"embeddings", "user_memory", "session_summaries"}
