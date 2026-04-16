"""RAG (Retrieval-Augmented Generation) service for context retrieval and exchange storage.

Queries pgvector across embeddings, user_memory, and session_summaries tables
for relevant context, and stores conversation exchanges as chunked embeddings.

Validates: Requirements 4.2, 4.3, 4.4, 4.5, 5.5
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Embedding
from app.services.bedrock import BedrockService
from app.utils.chunking import chunk_text

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """A single RAG retrieval result."""

    chunk_text: str
    similarity: float
    source_table: str


class RAGService:
    """RAG engine for context retrieval and exchange storage.

    Args:
        db: An async SQLAlchemy session.
        bedrock: A BedrockService instance for generating embeddings.
    """

    def __init__(self, db: AsyncSession, bedrock: BedrockService) -> None:
        self._db = db
        self._bedrock = bedrock

    async def retrieve_context(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[RAGResult]:
        """Query pgvector across embeddings, user_memory, and session_summaries.

        Returns the top-k results with cosine similarity >= threshold,
        ordered by similarity descending.

        Args:
            query_embedding: The 1536-dim query vector.
            top_k: Maximum number of results to return (default 5).
            threshold: Minimum cosine similarity score (default 0.7).

        Returns:
            A list of RAGResult ordered by similarity descending.
        """
        embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"

        # Use raw SQL with UNION ALL across all three vector tables.
        # pgvector cosine distance operator <=> returns distance (0 = identical),
        # so similarity = 1 - distance.
        query = text("""
            SELECT chunk_text, similarity, source_table
            FROM (
                SELECT
                    e.chunk_text AS chunk_text,
                    1 - (e.embedding <=> :embedding::vector) AS similarity,
                    'embeddings' AS source_table
                FROM embeddings e

                UNION ALL

                SELECT
                    um.content AS chunk_text,
                    1 - (um.embedding <=> :embedding::vector) AS similarity,
                    'user_memory' AS source_table
                FROM user_memory um

                UNION ALL

                SELECT
                    ss.summary_text AS chunk_text,
                    1 - (ss.embedding <=> :embedding::vector) AS similarity,
                    'session_summaries' AS source_table
                FROM session_summaries ss
            ) AS combined
            WHERE similarity >= :threshold
            ORDER BY similarity DESC
            LIMIT :top_k
        """)

        result = await self._db.execute(
            query,
            {
                "embedding": embedding_str,
                "threshold": threshold,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()
        return [
            RAGResult(
                chunk_text=row.chunk_text,
                similarity=float(row.similarity),
                source_table=row.source_table,
            )
            for row in rows
        ]

    async def store_exchange(
        self,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Chunk a user+assistant exchange, embed each chunk, and store in the embeddings table.

        Concatenates user and assistant text, splits into chunks of <= 500 tokens,
        generates an embedding for each chunk, and inserts Embedding records.

        Args:
            conversation_id: The UUID of the conversation.
            user_text: The user's message text.
            assistant_text: The assistant's response text.
        """
        combined = f"User: {user_text}\n\nAssistant: {assistant_text}"
        chunks = chunk_text(combined, max_tokens=500)

        for chunk in chunks:
            embedding_vector = await self._bedrock.generate_embedding(chunk)
            record = Embedding(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                chunk_text=chunk,
                embedding=embedding_vector,
                created_at=datetime.now(timezone.utc),
            )
            self._db.add(record)

        await self._db.flush()
