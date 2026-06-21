"""Text document chunking with table-aware splitting.
Uses RecursiveCharacterTextSplitter from LangChain for prose,
and row-boundary splitting for tabular data (pipe-delimited rows).
"""
import re
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=_SEPARATORS
)

# A table row contains at least one pipe with text on both sides
_TABLE_ROW_RE = re.compile(r"^.+\|.+$")


def _get_splitter(chunk_size: int, overlap: int) -> RecursiveCharacterTextSplitter:
    if chunk_size == CHUNK_SIZE and overlap == CHUNK_OVERLAP:
        return _DEFAULT_SPLITTER
    safe_overlap = min(overlap, chunk_size // 5) if overlap >= chunk_size else overlap
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=safe_overlap, separators=_SEPARATORS
    )


def _extract_table_blocks(lines: List[str]) -> List[dict]:
    """Identify contiguous blocks of table rows (>=2 consecutive pipe-delimited lines).
    Returns list of {start, end} line indices for each table block.
    """
    blocks = []
    block_start = None
    block_len = 0

    for i, line in enumerate(lines):
        if _TABLE_ROW_RE.match(line.strip()):
            if block_start is None:
                block_start = i
                block_len = 1
            else:
                block_len += 1
        else:
            if block_start is not None and block_len >= 2:
                blocks.append({"start": block_start, "end": i})
            block_start = None
            block_len = 0

    if block_start is not None and block_len >= 2:
        blocks.append({"start": block_start, "end": len(lines)})

    return blocks


def _split_table_by_rows(table_text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split a large table at row boundaries, never mid-row."""
    table_rows = table_text.split("\n")
    chunks = []
    current_rows: list[str] = []
    current_len = 0

    for row in table_rows:
        row_len = len(row) + 1  # +1 for newline
        if current_len + row_len > chunk_size and current_rows:
            chunks.append("\n".join(current_rows))
            # Overlap: keep a few trailing rows for context
            avg_row_len = max(1, current_len // len(current_rows))
            overlap_rows = max(1, overlap // avg_row_len)
            current_rows = current_rows[-overlap_rows:]
            current_len = sum(len(r) + 1 for r in current_rows)
        current_rows.append(row)
        current_len += row_len

    if current_rows:
        chunks.append("\n".join(current_rows))

    return chunks


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []

    lines = text.split("\n")
    table_blocks = _extract_table_blocks(lines)

    # No tables detected — use standard splitter (backward-compatible)
    if not table_blocks:
        return _get_splitter(chunk_size, overlap).split_text(text)

    # Split text into segments: prose sections and protected table blocks
    splitter = _get_splitter(chunk_size, overlap)
    chunks: list[str] = []
    last_end = 0

    for block in table_blocks:
        # Process prose before this table
        prose = "\n".join(lines[last_end:block["start"]]).strip()
        if prose:
            chunks.extend(splitter.split_text(prose))

        # Process the table block
        table_text = "\n".join(lines[block["start"]:block["end"]])
        if len(table_text) <= chunk_size:
            chunks.append(table_text)
        else:
            chunks.extend(_split_table_by_rows(table_text, chunk_size, overlap))

        last_end = block["end"]

    # Process remaining prose after last table
    remaining = "\n".join(lines[last_end:]).strip()
    if remaining:
        chunks.extend(splitter.split_text(remaining))

    return chunks
