"""Unit tests for the text chunking utility.

Validates: Requirements 4.4
"""

from app.utils.chunking import chunk_text, count_tokens


class TestCountTokens:
    def test_empty_string(self) -> None:
        assert count_tokens("") == 0

    def test_whitespace_only(self) -> None:
        assert count_tokens("   ") == 0

    def test_single_word(self) -> None:
        assert count_tokens("hello") == 1

    def test_multiple_words(self) -> None:
        assert count_tokens("hello world foo bar") == 4


class TestChunkText:
    def test_empty_string_returns_single_chunk(self) -> None:
        assert chunk_text("") == [""]

    def test_short_text_returns_single_chunk(self) -> None:
        text = "Hello world"
        result = chunk_text(text)
        assert result == [text]

    def test_no_content_lost(self) -> None:
        text = "word " * 1000
        text = text.rstrip()
        result = chunk_text(text, max_tokens=100)
        assert "".join(result) == text

    def test_no_chunk_exceeds_max_tokens(self) -> None:
        text = " ".join(f"word{i}" for i in range(1000))
        result = chunk_text(text, max_tokens=100)
        for chunk in result:
            assert count_tokens(chunk) <= 100

    def test_splits_on_paragraph_boundaries(self) -> None:
        para1 = " ".join(f"a{i}" for i in range(50))
        para2 = " ".join(f"b{i}" for i in range(50))
        text = para1 + "\n\n" + para2
        result = chunk_text(text, max_tokens=60)
        assert len(result) == 2
        assert "".join(result) == text

    def test_splits_on_sentence_boundaries(self) -> None:
        s1 = " ".join(f"a{i}" for i in range(40))
        s2 = " ".join(f"b{i}" for i in range(40))
        text = s1 + ". " + s2 + "."
        result = chunk_text(text, max_tokens=50)
        assert "".join(result) == text
        for chunk in result:
            assert count_tokens(chunk) <= 50

    def test_falls_back_to_word_boundaries(self) -> None:
        # One giant sentence with no punctuation
        text = " ".join(f"word{i}" for i in range(200))
        result = chunk_text(text, max_tokens=50)
        assert "".join(result) == text
        for chunk in result:
            assert count_tokens(chunk) <= 50

    def test_max_tokens_one(self) -> None:
        text = "a b c"
        result = chunk_text(text, max_tokens=1)
        assert "".join(result) == text
        for chunk in result:
            assert count_tokens(chunk) <= 1

    def test_invalid_max_tokens_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            chunk_text("hello", max_tokens=0)

    def test_preserves_multiple_newlines(self) -> None:
        text = "hello\n\n\nworld"
        result = chunk_text(text, max_tokens=500)
        assert "".join(result) == text
