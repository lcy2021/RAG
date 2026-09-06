"""Naive recursive character splitter used by the builtin chunker plugin."""

DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def split_recursive(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    separators: list[str] | None = None,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    cleaned = text.strip()
    if not cleaned:
        return []
    parts = _split(cleaned, chunk_size, separators or DEFAULT_SEPARATORS)
    return _with_overlap(parts, overlap)


def _split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    sep, rest = separators[0], separators[1:]
    pieces = text.split(sep) if sep else list(text)
    merged: list[str] = []
    buf = ""
    join = sep
    for piece in pieces:
        candidate = piece if not buf else buf + join + piece
        if len(candidate) <= chunk_size:
            buf = candidate
            continue
        if buf:
            merged.extend(_split(buf, chunk_size, rest))
        if len(piece) > chunk_size:
            merged.extend(_split(piece, chunk_size, rest))
            buf = ""
        else:
            buf = piece
    if buf:
        merged.extend(_split(buf, chunk_size, rest))
    return merged


def _with_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap == 0 or len(chunks) <= 1:
        return chunks
    out: list[str] = []
    prev_tail = ""
    for chunk in chunks:
        combined = (prev_tail + chunk) if prev_tail else chunk
        out.append(combined)
        prev_tail = combined[-overlap:] if len(combined) > overlap else combined
    return out
