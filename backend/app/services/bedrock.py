"""AWS Bedrock service for chat inference, embeddings, image generation, and summarization."""

import base64
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import boto3
from botocore.exceptions import ClientError, ReadTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Map user-facing model identifiers to Bedrock model IDs
MODEL_MAP: dict[str, str] = {
    "sonnet": "anthropic.claude-sonnet-4-20250514",
    "opus": "anthropic.claude-opus",
}


class BedrockError(Exception):
    """Raised when a Bedrock API call fails."""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class BedrockService:
    """Client for AWS Bedrock runtime operations."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_region,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Bedrock. Yields text chunks.

        Args:
            messages: Conversation messages in Anthropic format.
            model: User-facing model key ("sonnet" or "opus").
            system_prompt: System prompt including RAG context.

        Yields:
            Text chunks from the model response.

        Raises:
            BedrockError: On inference or timeout errors.
        """
        model_id = MODEL_MAP.get(model)
        if model_id is None:
            raise BedrockError(
                error_code="INVALID_MODEL",
                message=f"Unknown model identifier: {model}",
            )

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": messages,
            }
        )

        try:
            response = self._client.invoke_model_with_response_stream(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ReadTimeoutError as exc:
            logger.error("Bedrock stream timeout for model %s: %s", model_id, exc)
            raise BedrockError(
                error_code="BEDROCK_TIMEOUT",
                message="Bedrock request timed out",
            ) from exc
        except ClientError as exc:
            logger.error("Bedrock stream error for model %s: %s", model_id, exc)
            raise BedrockError(
                error_code="BEDROCK_ERROR",
                message=f"Bedrock inference failed: {exc}",
            ) from exc

        try:
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text
        except (ClientError, KeyError, json.JSONDecodeError) as exc:
            logger.error("Error reading Bedrock stream: %s", exc)
            raise BedrockError(
                error_code="BEDROCK_ERROR",
                message=f"Error reading Bedrock response stream: {exc}",
            ) from exc

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a 1536-dimensional embedding via Titan Embeddings v2.

        Args:
            text: The text to embed.

        Returns:
            A list of 1536 floats representing the embedding vector.

        Raises:
            BedrockError: On embedding generation failure.
        """
        body = json.dumps(
            {
                "inputText": text,
                "dimensions": 1536,
            }
        )

        try:
            response = self._client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ClientError as exc:
            logger.error("Bedrock embedding error: %s", exc)
            raise BedrockError(
                error_code="BEDROCK_ERROR",
                message=f"Embedding generation failed: {exc}",
            ) from exc

        result = json.loads(response["body"].read())
        embedding: list[float] = result["embedding"]
        return embedding

    async def generate_image(self, prompt: str) -> bytes:
        """Generate an image via Titan Image Generator.

        Args:
            prompt: Text description of the image to generate.

        Returns:
            PNG image bytes.

        Raises:
            BedrockError: On image generation failure.
        """
        body = json.dumps(
            {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt,
                },
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "quality": "standard",
                    "height": 1024,
                    "width": 1024,
                    "cfgScale": 8.0,
                },
            }
        )

        try:
            response = self._client.invoke_model(
                modelId="amazon.titan-image-generator-v1",
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ClientError as exc:
            logger.error("Bedrock image generation error: %s", exc)
            raise BedrockError(
                error_code="IMAGE_GEN_ERROR",
                message=f"Image generation failed: {exc}",
            ) from exc

        result = json.loads(response["body"].read())
        image_b64: str = result["images"][0]
        return base64.b64decode(image_b64)

    async def generate_summary(self, messages: list[dict[str, Any]]) -> str:
        """Generate a conversation summary using Sonnet.

        Args:
            messages: The conversation messages to summarize.

        Returns:
            A text summary of the conversation.

        Raises:
            BedrockError: On summarization failure.
        """
        summary_prompt = (
            "Provide a concise summary of the following conversation. "
            "Capture the key topics discussed, decisions made, and any "
            "important information exchanged. Keep it under 300 words."
        )

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": summary_prompt,
                "messages": messages,
            }
        )

        try:
            response = self._client.invoke_model(
                modelId=MODEL_MAP["sonnet"],
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ReadTimeoutError as exc:
            logger.error("Bedrock summary timeout: %s", exc)
            raise BedrockError(
                error_code="BEDROCK_TIMEOUT",
                message="Summary generation timed out",
            ) from exc
        except ClientError as exc:
            logger.error("Bedrock summary error: %s", exc)
            raise BedrockError(
                error_code="BEDROCK_ERROR",
                message=f"Summary generation failed: {exc}",
            ) from exc

        result = json.loads(response["body"].read())
        # Anthropic response format: content is a list of content blocks
        content_blocks = result.get("content", [])
        summary_parts = [
            block["text"] for block in content_blocks if block.get("type") == "text"
        ]
        return "".join(summary_parts)
