"""Session lifecycle management: idle detection, summary generation, and 30-day expiry.

Validates: Requirements 6.1, 6.2, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import Conversation, Embedding, Message, SessionSummary
from app.services.bedrock import BedrockError, BedrockService

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation idle detection, summary generation, and expiry archival.

    Args:
        db: An async SQLAlchemy session.
        bedrock: A BedrockService instance for generating summaries and embeddings.
    """

    def __init__(self, db: AsyncSession, bedrock: BedrockService) -> None:
        self._db = db
        self._bedrock = bedrock

    async def track_activity(self, conversation_id: str) -> None:
        """Update last_message_at timestamp for a conversation, resetting the idle timer.

        Args:
            conversation_id: The UUID string of the conversation.
        """
        now = datetime.now(timezone.utc)
        await self._db.execute(
            update(Conversation)
            .where(Conversation.id == uuid.UUID(conversation_id))
            .values(last_message_at=now, updated_at=now)
        )
        await self._db.flush()

    async def check_idle_conversations(self) -> list[str]:
        """Find conversations that have been idle for >= idle_timeout_minutes.

        Returns:
            A list of conversation ID strings that are idle.
        """
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.idle_timeout_minutes
        )
        result = await self._db.execute(
            select(Conversation.id).where(
                Conversation.last_message_at <= threshold
            )
        )
        rows = result.scalars().all()
        return [str(cid) for cid in rows]

    async def generate_and_email_summary(self, conversation_id: str) -> None:
        """Generate a summary for a conversation, store it, and attempt to email it.

        The summary is always persisted to session_summaries regardless of whether
        the email send succeeds or fails (Requirement 6.6).

        Args:
            conversation_id: The UUID string of the conversation.
        """
        conv_uuid = uuid.UUID(conversation_id)

        # Load conversation and its messages
        conv = await self._db.get(Conversation, conv_uuid)
        if conv is None:
            logger.warning("Conversation %s not found for summary generation", conversation_id)
            return

        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        if not messages:
            logger.info("Conversation %s has no messages, skipping summary", conversation_id)
            return

        # Build Anthropic-format messages for summarization
        anthropic_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        # Generate summary via Bedrock
        try:
            summary_text = await self._bedrock.generate_summary(anthropic_messages)
        except BedrockError:
            logger.exception("Failed to generate summary for conversation %s", conversation_id)
            return

        # Generate embedding for the summary
        try:
            embedding = await self._bedrock.generate_embedding(summary_text)
        except BedrockError:
            logger.exception("Failed to generate embedding for summary of conversation %s", conversation_id)
            return

        # Store summary in session_summaries (always, regardless of email outcome)
        summary_record = SessionSummary(
            id=uuid.uuid4(),
            conversation_id=conv_uuid,
            summary_text=summary_text,
            embedding=embedding,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(summary_record)
        await self._db.flush()

        # Attempt to send email — handle failure gracefully
        try:
            from app.services.email import EmailService

            email_service = EmailService()
            await email_service.send_session_summary(
                summary=summary_text,
                conversation_title=conv.title or "Untitled conversation",
            )
        except ImportError:
            logger.warning("EmailService not available yet, skipping email for conversation %s", conversation_id)
        except Exception:
            logger.exception("Failed to send summary email for conversation %s", conversation_id)

        await self._db.commit()

    async def run_expiry_job(self) -> None:
        """Daily job: find conversations older than 30 days, archive summaries, delete originals.

        For each expired conversation:
        1. Generate a SessionSummary if one doesn't already exist
        2. Store the summary with its embedding in session_summaries
        3. Delete the conversation, its messages, and chunk embeddings

        Session summaries are retained indefinitely for RAG (Requirement 7.5).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.conversation_retention_days
        )

        # Find expired conversations
        result = await self._db.execute(
            select(Conversation).where(Conversation.last_message_at < cutoff)
        )
        expired_conversations = result.scalars().all()

        if not expired_conversations:
            logger.info("No expired conversations found")
            return

        logger.info("Found %d expired conversations for archival", len(expired_conversations))

        for conv in expired_conversations:
            conv_id_str = str(conv.id)

            # Check if a summary already exists for this conversation
            existing = await self._db.execute(
                select(SessionSummary.id).where(
                    SessionSummary.conversation_id == conv.id
                )
            )
            has_summary = existing.scalar_one_or_none() is not None

            if not has_summary:
                # Generate summary before deleting
                result = await self._db.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at)
                )
                messages = result.scalars().all()

                if messages:
                    anthropic_messages = [
                        {"role": msg.role, "content": msg.content} for msg in messages
                    ]

                    try:
                        summary_text = await self._bedrock.generate_summary(anthropic_messages)
                        embedding = await self._bedrock.generate_embedding(summary_text)

                        summary_record = SessionSummary(
                            id=uuid.uuid4(),
                            conversation_id=conv.id,
                            summary_text=summary_text,
                            embedding=embedding,
                            created_at=datetime.now(timezone.utc),
                        )
                        self._db.add(summary_record)
                        await self._db.flush()
                    except BedrockError:
                        logger.exception(
                            "Failed to generate summary for expired conversation %s, skipping deletion",
                            conv_id_str,
                        )
                        continue
                else:
                    logger.info("Expired conversation %s has no messages, deleting without summary", conv_id_str)

            # Delete the conversation (cascade removes messages and embeddings)
            await self._db.delete(conv)
            logger.info("Archived and deleted expired conversation %s", conv_id_str)

        await self._db.commit()
        logger.info("Expiry job completed, processed %d conversations", len(expired_conversations))
