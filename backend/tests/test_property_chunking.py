# Feature: claude-simulator, Property 11: Text chunking produces segments ≤ 500 tokens
# Validates: Requirements 4.4
"""
Property-based test verifying that the text chunking function always produces
segments within the token limit and that concatenation of all chunks exactly
reconstructs the original text (no content lost or duplicated).
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.utils.chunking import chunk_text, count_tokens


class TestChunkingProperty:
    """Property 11: Text chunking produces segments ≤ 500 tokens."""

    @settings(max_examples=100)
    @given(text=st.text(min_size=0, max_size=10000))
    def test_chunking_segments_within_default_limit(self, text: str) -> None:
        """**Validates: Requirements 4.4**

        For any text input, every output chunk SHALL contain 500 tokens or
        fewer, and the concatenation of all chunks SHALL be equivalent to the
        original text.
        """
        chunks = chunk_text(text, max_tokens=500)
        for chunk in chunks:
            assert count_tokens(chunk) <= 500, (
                f"Chunk exceeds 500 tokens: {count_tokens(chunk)}"
            )
        assert "".join(chunks) == text, "Concatenation of chunks must equal original text"

    @settings(max_examples=100)
    @given(
        text=st.text(min_size=0, max_size=5000),
        max_tokens=st.integers(min_value=1, max_value=1000),
    )
    def test_chunking_segments_within_variable_limit(
        self, text: str, max_tokens: int
    ) -> None:
        """**Validates: Requirements 4.4**

        For any text input and any valid max_tokens value, every output chunk
        SHALL contain max_tokens tokens or fewer, and the concatenation of all
        chunks SHALL be equivalent to the original text.
        """
        chunks = chunk_text(text, max_tokens=max_tokens)
        for chunk in chunks:
            assert count_tokens(chunk) <= max_tokens, (
                f"Chunk has {count_tokens(chunk)} tokens, exceeds limit of {max_tokens}"
            )
        assert "".join(chunks) == text, "Concatenation of chunks must equal original text"
