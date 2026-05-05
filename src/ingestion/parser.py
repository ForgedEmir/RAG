"""
Document parsing module for the RAG system.
Supported formats: .md, .txt, .json, .csv, .xlsx, .xml, .pdf.
Uses LlamaParse for complex PDFs and Unstructured as fallback.
"""
import os
import re
import csv
import json
import logging
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

_LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")


def _parse_pdf_llamaparse(filepath: str) -> Optional[str]:
    if not _LLAMA_API_KEY:
        return None
    try:
        from llama_parse import LlamaParse
        parser = LlamaParse(api_key=_LLAMA_API_KEY, result_type="markdown")
        documents = parser.load_data(filepath)
        return "\n\n".join(doc.text for doc in documents if doc.text)
    except ImportError:
        logger.warning("Library 'llama-parse' not installed. Run 'pip install llama-parse'.")
        return None
    except Exception as e:
        logger.warning(f"LlamaParse failed for {filepath}, falling back to Unstructured: {e}")
        return None


def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = text.replace('%PLAYER_NAME%', 'the player')
    text = re.sub(r'%[A-Z_0-9]+%', lambda m: m.group(0).replace('%', ''), text)
    paragraphs = re.split(r'\n\s*\n', text)
    cleaned_paragraphs = [" ".join(p.split()) for p in paragraphs if p.strip()]
    return "\n\n".join(cleaned_paragraphs)


def _parse_pdf_unstructured(filepath: str) -> Optional[str]:
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("Library 'unstructured' not installed. Run 'pip install unstructured'.")
        return None
    except Exception as e:
        logger.error(f"Unstructured extraction failed for {filepath}: {e}")
        return None


def _parse_pdf_pypdf(filepath: str) -> Optional[str]:
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n\n"
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.warning(f"pypdf failed for {filepath}: {e}")
        return None


def _parse_pdf(filepath: str) -> Optional[str]:
    result = _parse_pdf_llamaparse(filepath)
    if result:
        return result
    result = _parse_pdf_pypdf(filepath)
    if result:
        return result
    return _parse_pdf_unstructured(filepath)


def _parse_docx(filepath: str) -> Optional[str]:
    try:
        import docx as _docx
        doc = _docx.Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    paragraphs.append(" | ".join(cells))
        return "\n\n".join(paragraphs) if paragraphs else None
    except Exception as e:
        logger.warning(f"python-docx failed for {filepath}, falling back to unstructured: {e}")
        try:
            from unstructured.partition.docx import partition_docx
            elements = partition_docx(filename=filepath)
            return "\n".join(str(el) for el in elements if str(el).strip()) or None
        except Exception as e2:
            logger.error(f"DOCX extraction failed for {filepath}: {e2}")
            return None


def extract_text_from_file(filepath: str) -> Optional[str]:
    if not os.path.exists(filepath):
        logger.error(f"File not found at specified path: {filepath}")
        return None

    ext = os.path.splitext(filepath)[1].lower()
    loaders = {
        '.txt': _read_text_file,
        '.md':  _read_text_file,
        '.json': _read_json_file,
        '.csv': _read_csv,
        '.xlsx': _xlsx_to_text,
        '.xml': _xml_to_text,
        '.pdf': _parse_pdf,
        '.docx': _parse_docx,
        '.doc': _parse_docx,
    }

    loader = loaders.get(ext)
    if not loader:
        logger.warning(f"Unsupported file format: {ext}")
        return None

    try:
        return loader(filepath)
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return None


def _read_text_file(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _read_json_file(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return _json_to_text(data)


def _read_csv(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8') as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        reader = csv.reader(f, dialect)
        lines = [" | ".join(cell for cell in row if cell.strip()) for row in reader]
        return "\n".join(line for line in lines if line)


def _xlsx_to_text(filepath: str) -> str:
    """
    Convert an Excel file (.xlsx) to structured text with semantic context.
    Adds a header describing the file, sheets and columns so the content is
    findable by both vector search and BM25.

    Example output:
        [FILE: base_prospect_V2.xlsx]
        This file contains 3 sheets: Prospects, Statistics, Notes.
        Sheet 'Prospects' (120 rows) — Columns: Name, Age, City, Email, Phone
        ---
        Name: John | Age: 35 | City: Paris | Email: john@test.com
        Name: Mary | Age: 28 | City: Lyon | Email: mary@test.com
    """
    try:
        import openpyxl
        workbook = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        lines = []

        filename = os.path.basename(filepath)

        # Semantic header — makes the file findable by search
        sheet_info = []
        total_rows = 0
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows = list(sheet.iter_rows(max_row=min(sheet.max_row, 2000)))
            if rows:
                headers = [str(cell.value or "") for cell in rows[0]]
                n_rows = max(0, len(rows) - 1)
                total_rows += n_rows
                sheet_info.append(
                    f"Sheet '{sheet_name}' ({n_rows} rows)"
                    f" — Columns: {', '.join(h for h in headers if h)}"
                )

        lines.append(f"[FILE: {filename}]")
        lines.append(
            f"This file contains {len(workbook.sheetnames)} sheet(s): "
            f"{', '.join(workbook.sheetnames)}."
        )
        for info in sheet_info:
            lines.append(info)
        lines.append("---")

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows = list(sheet.iter_rows(max_row=min(sheet.max_row, 2000)))
            if not rows:
                continue
            headers = [str(cell.value or "") for cell in rows[0]]

            # Header row with explicit column names
            if len(workbook.sheetnames) > 1:
                lines.append(f"\n=== Sheet: {sheet_name} ===")

            for row in rows[1:]:
                parts = [
                    f"{headers[i] if i < len(headers) else f'Col{i}'}: {cell.value}"
                    for i, cell in enumerate(row) if cell.value is not None
                ]
                if parts:
                    lines.append(" | ".join(parts))

        workbook.close()
        return "\n".join(lines)
    except ImportError:
        logger.warning("Library 'openpyxl' not installed.")
        return ""


def _json_to_text(data: Any, level: int = 0) -> str:
    lines = []
    indent = "  " * level

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{indent}{key}:")
                lines.append(_json_to_text(value, level + 1))
            else:
                lines.append(f"{indent}{key}: {value}")

    elif isinstance(data, list):
        for element in data:
            lines.append(_json_to_text(element, level))
            lines.append(f"{indent}---")

    else:
        lines.append(f"{indent}{data}")

    return "\n".join(line for line in lines if line)


def _xml_to_text(filepath: str) -> str:
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("Library 'unstructured' not installed.")
        return ""
    except Exception as e:
        logger.error(f"Error processing XML for {filepath}: {e}")
        return ""
