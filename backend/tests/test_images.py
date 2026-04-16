"""Unit tests for image endpoints.

Validates: Requirements 8.1, 8.2, 8.5, 8.6, 9.1, 9.2, 9.5
"""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.images import (
    ALLOWED_CONTENT_TYPES,
    MAX_IMAGE_SIZE_BYTES,
    encode_image_for_bedrock,
    validate_image_upload,
)


class TestValidateImageUpload:
    """Tests for validate_image_upload()."""

    def test_accepts_png(self) -> None:
        validate_image_upload("image/png", 1000)

    def test_accepts_jpeg(self) -> None:
        validate_image_upload("image/jpeg", 1000)

    def test_accepts_gif(self) -> None:
        validate_image_upload("image/gif", 1000)

    def test_accepts_webp(self) -> None:
        validate_image_upload("image/webp", 1000)

    def test_rejects_unsupported_format(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_upload("image/bmp", 1000)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "INVALID_FILE"

    def test_rejects_non_image_type(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_upload("application/pdf", 1000)
        assert exc_info.value.status_code == 400

    def test_rejects_none_content_type(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_upload(None, 1000)
        assert exc_info.value.status_code == 400

    def test_accepts_exactly_5mb(self) -> None:
        validate_image_upload("image/png", MAX_IMAGE_SIZE_BYTES)

    def test_rejects_over_5mb(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_upload("image/png", MAX_IMAGE_SIZE_BYTES + 1)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "INVALID_FILE"

    def test_accepts_zero_size(self) -> None:
        validate_image_upload("image/png", 0)


class TestEncodeImageForBedrock:
    """Tests for encode_image_for_bedrock()."""

    def test_returns_correct_structure(self) -> None:
        image_bytes = b"\x89PNG\r\n\x1a\nfake"
        result = encode_image_for_bedrock(image_bytes, "image/png")

        assert result["type"] == "image"
        assert result["source"]["type"] == "base64"
        assert result["source"]["media_type"] == "image/png"

    def test_base64_encodes_correctly(self) -> None:
        image_bytes = b"test image data"
        result = encode_image_for_bedrock(image_bytes, "image/jpeg")

        expected_b64 = base64.b64encode(image_bytes).decode("utf-8")
        assert result["source"]["data"] == expected_b64

    def test_preserves_media_type(self) -> None:
        result = encode_image_for_bedrock(b"data", "image/webp")
        assert result["source"]["media_type"] == "image/webp"

    def test_roundtrip_decode(self) -> None:
        original = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = encode_image_for_bedrock(original, "image/png")
        decoded = base64.b64decode(result["source"]["data"])
        assert decoded == original
