"""Text chunking utility for RAG pipeline.

Splits text into segments of ≤500 tokens (configurable), preserving content
integrity. Uses whitespace-based token counting where each word = 1 token.

Validates: Requirements 4.4
"""

import re


def count_tokens(text: str) -> int:
    """Count tokens in text using whitespace splitting (1 word = 1 token)."""
    if not text or not text.strip():
        return 0
    return len(text.split())


def chunk_text(text: str, max_tokens: int = 500) -> list[str]:
    """Split text into chunks where each chunk has ≤ max_tokens tokens.

    The concatenation of all returned chunks equals the original text exactly
    (no content lost or duplicated).

    Strategy:
    1. Try to split on paragraph boundaries (double newlines)
    2. Fall back to sentence boundaries
    3. Fall back to word boundaries

    Args:
        text: The input text to chunk.
        max_tokens: Maximum number of tokens per chunk (default 500).

    Returns:
        A list of text chunks whose concatenation equals the original text.
    """
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")

    if not text:
        return [text] if text == "" else []

    if count_tokens(text) <= max_tokens:
        return [text]

    # Split into paragraphs, keeping the delimiters
    paragraphs = _split_keeping_separators(text, r'\n\n+')

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        # If adding this paragraph stays within limit, accumulate
        if count_tokens(current + paragraph) <= max_tokens:
            current += paragraph
        else:
            # Flush current if non-empty
            if current:
                chunks.append(current)
                current = ""

            # If the paragraph itself fits, start a new chunk with it
            if count_tokens(paragraph) <= max_tokens:
                current = paragraph
            else:
                # Paragraph too large — split by sentences
                chunks.extend(_split_by_sentences(paragraph, max_tokens))

    if current:
        chunks.append(current)

    return chunks


def _split_keeping_separators(text: str, pattern: str) -> list[str]:
    """Split text by a regex pattern, keeping separators attached to the
    preceding segment so concatenation reproduces the original."""
    parts = re.split(f'({pattern})', text)
    if not parts:
        return [text] if text else []

    # Merge separators with the preceding part
    merged: list[str] = []
    for part in parts:
        if not part:
            continue
        if merged and re.fullmatch(pattern, part):
            merged[-1] += part
        else:
            merged.append(part)

    return merged


def _split_by_sentences(text: str, max_tokens: int) -> list[str]:
    """Split text by sentence boundaries, falling back to word boundaries.

    Uses a regex that keeps the whitespace after sentence-ending punctuation
    attached to the preceding segment, so concatenation is exact.
    """
    # Split after sentence-ending punctuation + whitespace, keeping the
    # separator attached to the left part.
    # e.g. "Hello world. Foo bar." -> ["Hello world. ", "Foo bar."]
    parts = re.split(r'(?<=[.!?]\s)(?=\S)', text)

    if len(parts) <= 1:
        # No sentence boundaries found — fall back to words
        return _split_by_words(text, max_tokens)

    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = current + part

        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if count_tokens(part) <= max_tokens:
                current = part
            else:
                # Sentence too large — split by words
                chunks.extend(_split_by_words(part, max_tokens))
                current = ""

    if current:
        chunks.append(current)

    return chunks


def _split_by_words(text: str, max_tokens: int) -> list[str]:
    """Split text by word boundaries, guaranteeing exact reconstruction.

    Splits on whitespace while preserving the exact whitespace characters
    so that concatenation of chunks reproduces the original text.
    """
    # Split into tokens and whitespace segments
    # e.g. "hello  world" -> ["hello", "  ", "world"]
    segments = re.split(r'(\s+)', text)

    chunks: list[str] = []
    current = ""
    current_tokens = 0

    for segment in segments:
        if not segment:
            continue

        seg_tokens = count_tokens(segment)

        if seg_tokens == 0:
            # Pure whitespace — just append to current
            current += segment
        elif current_tokens + seg_tokens <= max_tokens:
            current += segment
            current_tokens += seg_tokens
        else:
            # Flush current chunk
            if current:
                chunks.append(current)
            current = segment
            current_tokens = seg_tokens

    if current:
        chunks.append(current)

    return chunks
