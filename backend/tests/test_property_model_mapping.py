# Feature: claude-simulator, Property 6: Model identifier maps to correct Bedrock model
# Validates: Requirements 2.3, 2.5
"""
Property-based test verifying that model identifiers map to the correct
Bedrock model IDs, both in the MODEL_MAP constant and when passed through
the stream_chat method.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.bedrock import MODEL_MAP, BedrockService

# Expected mapping per the design document
EXPECTED_MODEL_MAP = {
    "sonnet": "anthropic.claude-sonnet-4-20250514",
    "opus": "anthropic.claude-opus",
}


class TestModelIdentifierMapping:
    """Property 6: Model identifier maps to correct Bedrock model."""

    @given(model_id=st.sampled_from(["sonnet", "opus"]))
    @settings(max_examples=100)
    def test_model_map_returns_correct_bedrock_id(self, model_id: str) -> None:
        """For any valid model identifier, MODEL_MAP SHALL contain the
        corresponding Bedrock model ID."""
        assert model_id in MODEL_MAP
        assert MODEL_MAP[model_id] == EXPECTED_MODEL_MAP[model_id]

    @given(model_id=st.sampled_from(["sonnet", "opus"]))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stream_chat_invokes_bedrock_with_correct_model_id(
        self, model_id: str
    ) -> None:
        """For any valid model identifier passed to stream_chat, the Bedrock
        invocation SHALL use the corresponding model ID."""
        with patch("app.services.bedrock.boto3") as mock_boto3:
            service = BedrockService()
            mock_client = mock_boto3.client.return_value
            service._client = mock_client

            # Return an empty stream body so the generator completes
            mock_client.invoke_model_with_response_stream.return_value = {
                "body": []
            }

            # Exhaust the async generator
            async for _ in service.stream_chat(
                messages=[{"role": "user", "content": "hello"}],
                model=model_id,
                system_prompt="test",
            ):
                pass

            # Verify the modelId kwarg matches the expected Bedrock model
            call_args = mock_client.invoke_model_with_response_stream.call_args
            assert call_args.kwargs["modelId"] == EXPECTED_MODEL_MAP[model_id]
