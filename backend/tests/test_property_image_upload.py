# Feature: claude-simulator, Property 20: Image upload validation
# Validates: Requirements 8.1, 8.5
"""
Property-based test verifying that the image upload validation function
accepts files if and only if the content type is in ALLOWED_CONTENT_TYPES
AND the file size is ≤ 5MB. All other files are rejected with a 400 error.
"""

from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.images import (
    ALLOWED_CONTENT_TYPES,
    MAX_IMAGE_SIZE_BYTES,
    validate_image_upload,
)

# --- Strategies ---

# Valid content types drawn from the allowed set
valid_content_type_strategy = st.sampled_from(sorted(ALLOWED_CONTENT_TYPES))

# Invalid content types: random MIME-like strings that are NOT in the allowed set
invalid_content_type_strategy = st.text(min_size=1, max_size=50).filter(
    lambda ct: ct not in ALLOWED_CONTENT_TYPES
)

# File sizes within the 5MB limit (0 to MAX_IMAGE_SIZE_BYTES inclusive)
valid_size_strategy = st.integers(min_value=0, max_value=MAX_IMAGE_SIZE_BYTES)

# File sizes exceeding the 5MB limit
invalid_size_strategy = st.integers(
    min_value=MAX_IMAGE_SIZE_BYTES + 1, max_value=MAX_IMAGE_SIZE_BYTES * 10
)


class TestPropertyImageUploadValidation:
    """Property 20: Image upload validation."""

    @settings(max_examples=100)
    @given(content_type=valid_content_type_strategy, size=valid_size_strategy)
    def test_valid_type_and_valid_size_accepted(
        self, content_type: str, size: int
    ) -> None:
        """**Validates: Requirements 8.1**

        For any valid content type (from ALLOWED_CONTENT_TYPES) and any
        size ≤ 5MB, validate_image_upload() SHALL accept the file
        (no exception raised).
        """
        # Should not raise
        validate_image_upload(content_type, size)

    @settings(max_examples=100)
    @given(content_type=invalid_content_type_strategy, size=st.integers(min_value=0, max_value=MAX_IMAGE_SIZE_BYTES * 10))
    def test_invalid_type_rejected(
        self, content_type: str, size: int
    ) -> None:
        """**Validates: Requirements 8.5**

        For any invalid content type (not in ALLOWED_CONTENT_TYPES) and
        any size, validate_image_upload() SHALL reject with HTTP 400.
        """
        try:
            validate_image_upload(content_type, size)
            # If we get here, the function accepted an invalid type
            raise AssertionError(
                f"Expected rejection for content_type={content_type!r}, size={size}"
            )
        except HTTPException as exc:
            assert exc.status_code == 400, (
                f"Expected 400, got {exc.status_code} for content_type={content_type!r}"
            )

    @settings(max_examples=100)
    @given(content_type=valid_content_type_strategy, size=invalid_size_strategy)
    def test_valid_type_but_oversized_rejected(
        self, content_type: str, size: int
    ) -> None:
        """**Validates: Requirements 8.1, 8.5**

        For any valid content type but size > 5MB,
        validate_image_upload() SHALL reject with HTTP 400.
        """
        try:
            validate_image_upload(content_type, size)
            raise AssertionError(
                f"Expected rejection for content_type={content_type!r}, size={size}"
            )
        except HTTPException as exc:
            assert exc.status_code == 400, (
                f"Expected 400, got {exc.status_code} for oversized file"
            )
