"""
Document parsing module for the RAG system.
Supports formats: .md, .txt, .json, .csv, .xlsx, .xml, .pdf.
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
    """
    Attempts to extract text from a PDF using the LlamaParse API.

    Args:
        filepath (str): Path to the PDF file.

    Returns:
        Optional[str]: Extracted text in Markdown format, or None if API is unavailable or on error.
    """
    if not _LLAMA_API_KEY:
        return None
    try:
        from llama_parse import LlamaParse
        parser = LlamaParse(api_key=_LLAMA_API_KEY, result_type="markdown")
        documents = parser.load_data(filepath)
        return "\n\n".join(doc.text for doc in documents if doc.text)
    except ImportError:
        logger.warning("'llama-parse' library not installed. Run 'pip install llama-parse'.")
        return None
    except Exception as e:
        logger.warning(f"LlamaParse failed for {filepath}, falling back to Unstructured: {e}")
        return None


def clean_text(raw_text: str) -> str:
    """
    Cleans and normalizes raw text extracted from documents.
    Strips HTML, Markdown headers, handles game variables and normalizes whitespace.

    Args:
        raw_text (str): The raw text to clean.

    Returns:
        str: The cleaned and formatted text.
    """
    if not raw_text:
        return ""

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', raw_text)
    
    # Strip Markdown heading symbols
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Replace game variables with readable terms
    text = text.replace('%PLAYER_NAME%', 'the player')
    text = re.sub(r'%[A-Z_0-9]+%', lambda m: m.group(0).replace('%', ''), text)

    # Normalize whitespace and split into paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    cleaned_paragraphs = [" ".join(p.split()) for p in paragraphs if p.strip()]
    return "\n\n".join(cleaned_paragraphs)


def _parse_pdf_unstructured(filepath: str) -> Optional[str]:
    """
    Fallback engine for PDF parsing using the Unstructured library.

    Args:
        filepath (str): Path to the PDF file.

    Returns:
        Optional[str]: Extracted text, or None on failure.
    """
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("'unstructured' library not installed. Run 'pip install unstructured'.")
        return None
    except Exception as e:
        logger.error(f"Unstructured extraction failed for {filepath}: {e}")
        return None


def _parse_pdf_pypdf(filepath: str) -> Optional[str]:
    """Extracts text from a PDF using pypdf (very reliable)."""
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
    """
    Orchestrates PDF parsing favoring LlamaParse, then pypdf, and finally Unstructured.
    """
    # 1. LlamaParse (Premium / Markdown)
    result = _parse_pdf_llamaparse(filepath)
    if result:
        return result
    
    # 2. PyPDF (Local / Fast / Reliable)
    result = _parse_pdf_pypdf(filepath)
    if result:
        return result

    # 3. Unstructured (historical fallback)
    return _parse_pdf_unstructured(filepath)


def _parse_docx(filepath: str) -> Optional[str]:
    """Extracts text from a Word file (.docx) via python-docx with unstructured fallback."""
    try:
        import docx as _docx
        doc = _docx.Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Tables
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
    """
    Main function to extract text from a file based on its extension.

    Args:
        filepath (str): Path to the file to process.

    Returns:
        Optional[str]: The raw text extracted from the file, or None if the format is unsupported or file not found.
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found at the specified path: {filepath}")
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
    """Reads a plain text or Markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _read_json_file(filepath: str) -> str:
    """Reads and converts a JSON file into structured text."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return _json_to_text(data)


def _read_csv(filepath: str) -> str:
    """Extracts data from a CSV file attempting to detect its dialect."""
    with open(filepath, 'r', encoding='utf-8') as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        reader = csv.reader(f, dialect)
        lines = [" ".join(cell for cell in row if cell.strip()) for row in reader]
        return "\n".join(line for line in lines if line)


def _xlsx_to_text(filepath: str) -> str:
    """
    Converts an Excel file (.xlsx) to text in 'Column: Value' format.

    Args:
        filepath (str): Path to the Excel file.

    Returns:
        str: Structured text representing the content of Excel sheets.
    """
    try:
        import openpyxl
        workbook = openpyxl.load_workbook(filepath, read_only=True)
        lines = []

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows = list(sheet.rows)
            if not rows:
                continue
            headers = [str(cell.value or "") for cell in rows[0]]
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
        logger.warning("'openpyxl' library not installed.")
        return ""


def _json_to_text(data: Any, level: int = 0) -> str:
    """
    Recursively converts a Python object (from JSON) into readable text with indentation.

    Args:
        data (Any): The object to convert (dict, list, str, etc.).
        level (int): Current indentation level.

    Returns:
        str: Textual representation of the object.
    """
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
        for item in data:
            lines.append(_json_to_text(item, level))
            lines.append(f"{indent}---")

    else:
        lines.append(f"{indent}{data}")

    return "\n".join(line for line in lines if line)


def _xml_to_text(filepath: str) -> str:
    """
    Extracts text from an XML file using Unstructured to manage hierarchy.

    Args:
        filepath (str): Path to the XML file.

    Returns:
        str: Extracted text or empty string on error.
    """
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("'unstructured' library not installed.")
        return ""
    except Exception as e:
        logger.error(f"Error processing XML file {filepath}: {e}")
        return ""
