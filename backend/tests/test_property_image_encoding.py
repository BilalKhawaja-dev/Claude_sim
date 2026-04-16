# Feature: claude-simulator, Property 21: Image base64 encoding for Bedrock
# Validates: Requirements 8.2
"""
Property-based tests verifying that encode_image_for_bedrock() produces
a valid Bedrock multimodal image content block for any image bytes and
any valid media type. The base64 data must round-trip back to the
original bytes.
"""

import base64

from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.images import ALLOWED_CONTENT_TYPES, encode_image_for_bedrock

# --- Strategies ---

# Random binary data representing image bytes (0 bytes to 1 MB)
image_bytes_strategy = st.binary(min_size=0, max_size=1024 * 1024)

# Valid media types drawn from the allowed set
valid_media_type_strategy = st.sampled_from(sorted(ALLOWED_CONTENT_TYPES))


class TestPropertyImageBase64Encoding:
    """Property 21: Image base64 encoding for Bedrock.

    **Validates: Requirements 8.2**
    """

    @settings(max_examples=100)
    @given(
        image_bytes=image_bytes_strategy,
        media_type=valid_media_type_strategy,
    )
    def test_result_has_correct_structure(
        self, image_bytes: bytes, media_type: str
    ) -> None:
        """For any random bytes and any valid media type,
        encode_image_for_bedrock() returns a dict with the correct
        Bedrock multimodal structure: type="image", source.type="base64",
        source.media_type matches input, source.data is a valid base64 string.

        **Validates: Requirements 8.2**
        """
        result = encode_image_for_bedrock(image_bytes, media_type)

        # Top-level type
        assert result["type"] == "image"

        # Source block
        source = result["source"]
        assert source["type"] == "base64"
        assert source["media_type"] == media_type

        # data is a valid base64 string (decoding should not raise)
        decoded = base64.b64decode(source["data"])
        assert isinstance(decoded, bytes)

    @settings(max_examples=100)
    @given(
        image_bytes=image_bytes_strategy,
        media_type=valid_media_type_strategy,
    )
    def test_base64_round_trip(
        self, image_bytes: bytes, media_type: str
    ) -> None:
        """For any random bytes, the base64 data in the result can be
        decoded back to the original bytes (round-trip fidelity).

        **Validates: Requirements 8.2**
        """
        result = encode_image_for_bedrock(image_bytes, media_type)
        decoded = base64.b64decode(result["source"]["data"])
        assert decoded == image_bytes

    @settings(max_examples=100)
    @given(
        image_bytes=image_bytes_strategy,
        media_type=valid_media_type_strategy,
    )
    def test_result_contains_required_keys(
        self, image_bytes: bytes, media_type: str
    ) -> None:
        """The result structure always contains the required keys for
        Bedrock multimodal messages: 'type' and 'source' at top level,
        'type', 'media_type', and 'data' inside source.

        **Validates: Requirements 8.2**
        """
        result = encode_image_for_bedrock(image_bytes, media_type)

        assert "type" in result
        assert "source" in result
        assert "type" in result["source"]
        assert "media_type" in result["source"]
        assert "data" in result["source"]
