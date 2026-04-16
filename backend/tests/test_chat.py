"""Tests for POST /api/chat endpoint."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.chat import (
    _build_history_messages,
    _build_system_prompt,
    _generate_title,
    router,
)
from app.models.orm import Conversation, Message
from app.services.rag import RAGResult


class TestBuildSystemPrompt:
    """Unit tests for _build_system_prompt helper."""

    def test_no_rag_context(self) -> None:
        prompt = _build_system_prompt([])
        assert "Claude" in prompt
        assert "context" not in prompt.lower() or "retrieved" not in prompt.lower()

    def test_with_rag_context(self) -> None:
        results = [
            RAGResult(chunk_text="Python is great", similarity=0.9, source_table="embeddings"),
            RAGResult(chunk_text="User likes coffee", similarity=0.8, source_table="user_memory"),
        ]
        prompt = _build_system_prompt(results)
        assert "Python is great" in prompt
        assert "User likes coffee" in prompt
        assert "retrieved from memory" in prompt

    def test_base_prompt_always_present(self) -> None:
        prompt_empty = _build_system_prompt([])
        prompt_with = _build_system_prompt([
            RAGResult(chunk_text="test", similarity=0.9, source_table="embeddings"),
        ])
        # Both should contain the base Claude prompt
        assert "helpful" in prompt_empty
        assert "helpful" in prompt_with


class TestBuildHistoryMessages:
    """Unit tests for _build_history_messages helper."""

    @pytest.mark.asyncio
    async def test_returns_messages_in_order(self) -> None:
        conv_id = uuid.uuid4()
        msg1 = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content="Hello",
            has_image=False,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        msg2 = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="assistant",
            content="Hi there!",
            has_image=False,
            created_at=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
        )

        # Mock the db session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [msg1, msg2]
        mock_db.execute.return_value = mock_result

        history = await _build_history_messages(mock_db, conv_id)

        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_image_message_multimodal_format(self) -> None:
        conv_id = uuid.uuid4()
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content="What is this?",
            has_image=True,
            image_data="base64data==",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [msg]
        mock_db.execute.return_value = mock_result

        history = await _build_history_messages(mock_db, conv_id)

        assert len(history) == 1
        content = history[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "image"
        assert content[0]["source"]["data"] == "base64data=="
        assert content[1]["type"] == "text"
        assert content[1]["text"] == "What is this?"

    @pytest.mark.asyncio
    async def test_empty_conversation(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        history = await _build_history_messages(mock_db, uuid.uuid4())
        assert history == []


class TestGenerateTitle:
    """Unit tests for _generate_title helper."""

    @pytest.mark.asyncio
    async def test_returns_title_on_success(self) -> None:
        mock_response = {
            "body": MagicMock(
                read=lambda: json.dumps({
                    "content": [{"type": "text", "text": "Python Help Session"}]
                }).encode()
            )
        }

        with patch("app.api.chat.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = mock_response
            mock_boto3.client.return_value = mock_client

            title = await _generate_title("How do I use Python decorators?")
            assert title == "Python Help Session"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_error(self) -> None:
        with patch("app.api.chat.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.invoke_model.side_effect = Exception("Bedrock down")
            mock_boto3.client.return_value = mock_client

            title = await _generate_title("Hello")
            assert title == "New conversation"

    @pytest.mark.asyncio
    async def test_truncates_long_title(self) -> None:
        long_title = "A" * 300
        mock_response = {
            "body": MagicMock(
                read=lambda: json.dumps({
                    "content": [{"type": "text", "text": long_title}]
                }).encode()
            )
        }

        with patch("app.api.chat.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = mock_response
            mock_boto3.client.return_value = mock_client

            title = await _generate_title("test")
            assert len(title) <= 255
