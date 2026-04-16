"""Unit tests for BedrockService."""

import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.bedrock import MODEL_MAP, BedrockError, BedrockService


@pytest.fixture
def bedrock_service():
    """Create a BedrockService with a mocked boto3 client."""
    with patch("app.services.bedrock.boto3") as mock_boto3:
        service = BedrockService()
        service._client = mock_boto3.client.return_value
        yield service


class TestModelMap:
    """Tests for the MODEL_MAP constant."""

    def test_sonnet_maps_correctly(self):
        assert MODEL_MAP["sonnet"] == "anthropic.claude-sonnet-4-20250514"

    def test_opus_maps_correctly(self):
        assert MODEL_MAP["opus"] == "anthropic.claude-opus"

    def test_only_two_models(self):
        assert len(MODEL_MAP) == 2


class TestStreamChat:
    """Tests for BedrockService.stream_chat()."""

    @pytest.mark.asyncio
    async def test_stream_chat_yields_text_chunks(self, bedrock_service):
        chunks = [
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " world"}},
            {"type": "message_stop"},
        ]
        mock_events = [
            {"chunk": {"bytes": json.dumps(c).encode()}} for c in chunks
        ]
        bedrock_service._client.invoke_model_with_response_stream.return_value = {
            "body": mock_events
        }

        result = []
        async for text in bedrock_service.stream_chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="sonnet",
            system_prompt="You are helpful.",
        ):
            result.append(text)

        assert result == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_chat_uses_correct_model_id(self, bedrock_service):
        bedrock_service._client.invoke_model_with_response_stream.return_value = {
            "body": []
        }

        async for _ in bedrock_service.stream_chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="opus",
            system_prompt="test",
        ):
            pass

        call_args = bedrock_service._client.invoke_model_with_response_stream.call_args
        assert call_args.kwargs["modelId"] == "anthropic.claude-opus"

    @pytest.mark.asyncio
    async def test_stream_chat_invalid_model_raises(self, bedrock_service):
        with pytest.raises(BedrockError) as exc_info:
            async for _ in bedrock_service.stream_chat(
                messages=[], model="invalid", system_prompt=""
            ):
                pass
        assert exc_info.value.error_code == "INVALID_MODEL"

    @pytest.mark.asyncio
    async def test_stream_chat_client_error_raises(self, bedrock_service):
        from botocore.exceptions import ClientError

        bedrock_service._client.invoke_model_with_response_stream.side_effect = (
            ClientError({"Error": {"Code": "500", "Message": "fail"}}, "InvokeModel")
        )

        with pytest.raises(BedrockError) as exc_info:
            async for _ in bedrock_service.stream_chat(
                messages=[], model="sonnet", system_prompt=""
            ):
                pass
        assert exc_info.value.error_code == "BEDROCK_ERROR"

    @pytest.mark.asyncio
    async def test_stream_chat_timeout_raises(self, bedrock_service):
        from botocore.exceptions import ReadTimeoutError

        bedrock_service._client.invoke_model_with_response_stream.side_effect = (
            ReadTimeoutError(endpoint_url="https://bedrock.us-east-1.amazonaws.com")
        )

        with pytest.raises(BedrockError) as exc_info:
            async for _ in bedrock_service.stream_chat(
                messages=[], model="sonnet", system_prompt=""
            ):
                pass
        assert exc_info.value.error_code == "BEDROCK_TIMEOUT"


class TestGenerateEmbedding:
    """Tests for BedrockService.generate_embedding()."""

    @pytest.mark.asyncio
    async def test_returns_1536_dim_vector(self, bedrock_service):
        embedding = [0.1] * 1536
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"embedding": embedding}).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        result = await bedrock_service.generate_embedding("test text")

        assert len(result) == 1536
        assert result == embedding

    @pytest.mark.asyncio
    async def test_uses_titan_embed_v2(self, bedrock_service):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"embedding": [0.0] * 1536}).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        await bedrock_service.generate_embedding("test")

        call_args = bedrock_service._client.invoke_model.call_args
        assert call_args.kwargs["modelId"] == "amazon.titan-embed-text-v2:0"

    @pytest.mark.asyncio
    async def test_client_error_raises(self, bedrock_service):
        from botocore.exceptions import ClientError

        bedrock_service._client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "fail"}}, "InvokeModel"
        )

        with pytest.raises(BedrockError) as exc_info:
            await bedrock_service.generate_embedding("test")
        assert exc_info.value.error_code == "BEDROCK_ERROR"


class TestGenerateImage:
    """Tests for BedrockService.generate_image()."""

    @pytest.mark.asyncio
    async def test_returns_png_bytes(self, bedrock_service):
        png_bytes = b"\x89PNG\r\n\x1a\nfake_image_data"
        image_b64 = base64.b64encode(png_bytes).decode()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"images": [image_b64]}).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        result = await bedrock_service.generate_image("a cat")

        assert result == png_bytes

    @pytest.mark.asyncio
    async def test_uses_titan_image_generator(self, bedrock_service):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(
            {"images": [base64.b64encode(b"img").decode()]}
        ).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        await bedrock_service.generate_image("a dog")

        call_args = bedrock_service._client.invoke_model.call_args
        assert call_args.kwargs["modelId"] == "amazon.titan-image-generator-v1"

    @pytest.mark.asyncio
    async def test_client_error_raises(self, bedrock_service):
        from botocore.exceptions import ClientError

        bedrock_service._client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "fail"}}, "InvokeModel"
        )

        with pytest.raises(BedrockError) as exc_info:
            await bedrock_service.generate_image("test")
        assert exc_info.value.error_code == "IMAGE_GEN_ERROR"


class TestGenerateSummary:
    """Tests for BedrockService.generate_summary()."""

    @pytest.mark.asyncio
    async def test_returns_summary_text(self, bedrock_service):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(
            {"content": [{"type": "text", "text": "This is a summary."}]}
        ).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        result = await bedrock_service.generate_summary(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
        )

        assert result == "This is a summary."

    @pytest.mark.asyncio
    async def test_uses_sonnet_model(self, bedrock_service):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(
            {"content": [{"type": "text", "text": "Summary"}]}
        ).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        await bedrock_service.generate_summary([{"role": "user", "content": "Hi"}])

        call_args = bedrock_service._client.invoke_model.call_args
        assert call_args.kwargs["modelId"] == MODEL_MAP["sonnet"]

    @pytest.mark.asyncio
    async def test_concatenates_multiple_content_blocks(self, bedrock_service):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(
            {
                "content": [
                    {"type": "text", "text": "Part one. "},
                    {"type": "text", "text": "Part two."},
                ]
            }
        ).encode()
        bedrock_service._client.invoke_model.return_value = {"body": mock_body}

        result = await bedrock_service.generate_summary(
            [{"role": "user", "content": "Hello"}]
        )

        assert result == "Part one. Part two."

    @pytest.mark.asyncio
    async def test_client_error_raises(self, bedrock_service):
        from botocore.exceptions import ClientError

        bedrock_service._client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "fail"}}, "InvokeModel"
        )

        with pytest.raises(BedrockError) as exc_info:
            await bedrock_service.generate_summary([{"role": "user", "content": "Hi"}])
        assert exc_info.value.error_code == "BEDROCK_ERROR"

    @pytest.mark.asyncio
    async def test_timeout_raises(self, bedrock_service):
        from botocore.exceptions import ReadTimeoutError

        bedrock_service._client.invoke_model.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock.us-east-1.amazonaws.com"
        )

        with pytest.raises(BedrockError) as exc_info:
            await bedrock_service.generate_summary([{"role": "user", "content": "Hi"}])
        assert exc_info.value.error_code == "BEDROCK_TIMEOUT"
