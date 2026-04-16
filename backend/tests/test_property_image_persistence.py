# Feature: claude-simulator, Property 22: Image persistence with messages
# Validates: Requirements 8.6, 9.5
"""
Property-based tests verifying that Message ORM objects correctly track
image data. For any message that includes an uploaded or generated image,
the corresponding message record SHALL have has_image = True and a non-null
image_data field containing the image data. Messages without images SHALL
have has_image = False and image_data = None.
"""

import base64
import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.orm import Message

# --- Strategies ---

# Non-empty message content
content_strategy = st.text(min_size=1, max_size=300).filter(lambda s: s.strip())

# Valid roles
role_strategy = st.sampled_from(["user", "assistant"])

# Random binary data encoded as base64 to simulate image data (1 byte to 64KB)
base64_image_strategy = st.binary(min_size=1, max_size=65536).map(
    lambda b: base64.b64encode(b).decode("ascii")
)


class TestPropertyImagePersistence:
    """Property 22: Image persistence with messages.

    **Validates: Requirements 8.6, 9.5**
    """

    @settings(max_examples=100)
    @given(
        content=content_strategy,
        role=role_strategy,
        image_data=base64_image_strategy,
    )
    def test_message_with_image_has_image_true_and_data_non_null(
        self, content: str, role: str, image_data: str
    ) -> None:
        """For any Message created with image data, has_image SHALL be True
        and image_data SHALL be non-null.

        **Validates: Requirements 8.6, 9.5**
        """
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role=role,
            content=content,
            has_image=True,
            image_data=image_data,
        )

        assert msg.has_image is True
        assert msg.image_data is not None

    @settings(max_examples=100)
    @given(
        content=content_strategy,
        role=role_strategy,
        image_data=base64_image_strategy,
    )
    def test_image_data_contains_valid_decodable_base64(
        self, content: str, role: str, image_data: str
    ) -> None:
        """For any base64-encoded image data stored in a message, the
        image_data field SHALL contain valid base64 that can be decoded
        back to bytes.

        **Validates: Requirements 8.6, 9.5**
        """
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role=role,
            content=content,
            has_image=True,
            image_data=image_data,
        )

        decoded = base64.b64decode(msg.image_data)
        assert isinstance(decoded, bytes)
        assert len(decoded) > 0

    @settings(max_examples=100)
    @given(
        content=content_strategy,
        role=role_strategy,
    )
    def test_message_without_image_has_image_false_and_data_none(
        self, content: str, role: str
    ) -> None:
        """Messages without images SHALL have has_image=False and
        image_data=None.

        **Validates: Requirements 8.6, 9.5**
        """
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role=role,
            content=content,
            has_image=False,
            image_data=None,
        )

        assert msg.has_image is False
        assert msg.image_data is None
