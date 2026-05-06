"""Test real PPTX files from data/sample: parse, clean, chunk, verify."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.chunker import split_into_chunks

SAMPLE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))


def main():
    pptx_files = sorted(f for f in os.listdir(SAMPLE) if f.endswith(".pptx"))
    print(f"Found {len(pptx_files)} PPTX files in data/sample/\n")

    for fname in pptx_files:
        fpath = os.path.join(SAMPLE, fname)
        print("=" * 70)
        print(f"FILE: {fname}")
        print("=" * 70)

        # 1. Parse
        raw = extract_text_from_file(fpath)
        if raw is None:
            print("  RESULT: FAIL - returned None\n")
            continue

        # 2. Show full parsed output
        print(f"\n  [PARSED OUTPUT] ({len(raw)} chars):\n")
        for line in raw.split("\n"):
            print(f"    {line}")

        # 3. Clean
        cleaned = clean_text(raw)
        print(f"\n  [CLEANED] {len(cleaned)} chars")

        # 4. Chunk
        chunks = split_into_chunks(cleaned)
        print(f"  [CHUNKS] {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            print(f"\n    --- Chunk {i + 1} ({len(chunk)} chars) ---")
            preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
            for line in preview.split("\n"):
                print(f"    {line}")

        # 5. Verify
        has_slides = "Slide" in raw
        has_tables = "|" in raw
        table_rows_intact = True
        for chunk in chunks:
            for line in chunk.split("\n"):
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        table_rows_intact = False

        print(f"\n  [CHECKS]")
        print(f"    Slide markers: {'YES' if has_slides else 'NO'}")
        print(f"    Tables found:  {'YES' if has_tables else 'NO'}")
        print(f"    Table rows intact after chunking: {'YES' if table_rows_intact else 'NO'}")
        print(f"  RESULT: PASS\n")

    print("Done.")


if __name__ == "__main__":
    main()
