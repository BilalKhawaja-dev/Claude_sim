# Feature: claude-simulator, Property 4: Bedrock errors produce structured error responses
# Validates: Requirements 1.6, 9.4
"""
Property-based test verifying that BedrockError always produces structured
error responses with non-empty error_code and message fields.

For any error returned by the Bedrock service, the Backend_API SHALL return
a response containing an error code and a human-readable description string,
never an unstructured or empty error.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.schemas import ErrorResponse
from app.services.bedrock import BedrockError

# Known error codes produced by BedrockService
KNOWN_ERROR_CODES = [
    "INVALID_MODEL",
    "BEDROCK_TIMEOUT",
    "BEDROCK_ERROR",
    "IMAGE_GEN_ERROR",
]

# Strategy: generate error codes — mix of known codes and arbitrary non-empty strings
error_code_strategy = st.one_of(
    st.sampled_from(KNOWN_ERROR_CODES),
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
)

# Strategy: generate human-readable error messages (non-empty, non-whitespace-only)
error_message_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


class TestBedrockErrorStructured:
    """**Validates: Requirements 1.6, 9.4**"""

    @given(error_code=error_code_strategy, message=error_message_strategy)
    @settings(max_examples=100)
    def test_bedrock_error_has_non_empty_error_code(
        self, error_code: str, message: str
    ) -> None:
        """BedrockError SHALL always have a non-empty error_code field."""
        error = BedrockError(error_code=error_code, message=message)
        assert isinstance(error.error_code, str)
        assert len(error.error_code) > 0
        assert error.error_code.strip() != ""

    @given(error_code=error_code_strategy, message=error_message_strategy)
    @settings(max_examples=100)
    def test_bedrock_error_has_non_empty_message(
        self, error_code: str, message: str
    ) -> None:
        """BedrockError SHALL always have a non-empty message field."""
        error = BedrockError(error_code=error_code, message=message)
        assert isinstance(error.message, str)
        assert len(error.message) > 0
        assert error.message.strip() != ""

    @given(error_code=error_code_strategy, message=error_message_strategy)
    @settings(max_examples=100)
    def test_bedrock_error_converts_to_structured_error_response(
        self, error_code: str, message: str
    ) -> None:
        """BedrockError SHALL be convertible to a structured ErrorResponse
        with matching error_code and message, never unstructured or empty."""
        error = BedrockError(error_code=error_code, message=message)
        response = ErrorResponse(error_code=error.error_code, message=error.message)

        assert response.error_code == error_code
        assert response.message == message
        assert response.error_code.strip() != ""
        assert response.message.strip() != ""

    @given(error_code=st.sampled_from(KNOWN_ERROR_CODES), message=error_message_strategy)
    @settings(max_examples=100)
    def test_known_error_codes_produce_valid_responses(
        self, error_code: str, message: str
    ) -> None:
        """All known Bedrock error codes SHALL produce valid structured
        ErrorResponse objects with the correct error_code preserved."""
        error = BedrockError(error_code=error_code, message=message)
        response = ErrorResponse(error_code=error.error_code, message=error.message)

        assert response.error_code in KNOWN_ERROR_CODES
        assert response.error_code == error_code
        assert len(response.message) > 0
