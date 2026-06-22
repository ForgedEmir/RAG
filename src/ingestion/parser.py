"""
Document parsing module for the RAG system.
Supported formats: .md, .txt, .json, .csv, .xlsx, .xls, .xml, .pdf, .docx, .doc, .pptx, .eml, .msg.
Uses LlamaParse for complex PDFs and Unstructured as fallback.
"""
import io
import os
import re
import csv
import json
import email as _email_mod
import logging
import subprocess
import xml.etree.ElementTree as ET
from email import policy as _email_policy
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

_LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

# Formula error values to filter out in Excel cells
_FORMULA_ERRORS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}

# Configurable Excel row limit (default 10 000)
_MAX_XLSX_ROWS = int(os.getenv("MAX_XLSX_ROWS", "10000"))


def _detect_and_read(filepath: str, fallback_encoding: str = "utf-8") -> str:
    """Read a file with automatic encoding detection via charset-normalizer.
    Falls back to the given encoding on detection failure.
    Handles UTF-8 BOM transparently.
    """
    with open(filepath, "rb") as f:
        raw = f.read()
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(raw).best()
        if result is not None:
            return str(result)
    except ImportError:
        pass
    return raw.decode(fallback_encoding, errors="replace")


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


def _parse_pdf_ocr(filepath: str) -> Optional[str]:
    """Last-resort OCR via pdf2image + pytesseract for scanned PDFs."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(filepath)
        text_parts = []
        for img in images:
            page_text = pytesseract.image_to_string(img)
            if page_text.strip():
                text_parts.append(page_text.strip())
        return "\n\n".join(text_parts) if text_parts else None
    except ImportError:
        logger.debug("OCR libraries not available (pdf2image, pytesseract).")
        return None
    except Exception as e:
        logger.warning(f"OCR failed for {filepath}: {e}")
        return None


def _parse_pdf(filepath: str) -> Optional[str]:
    # Priority: LlamaParse (best quality) → Unstructured (preserves tables)
    #         → pypdf (text-only fallback) → OCR (scanned documents)
    result = _parse_pdf_llamaparse(filepath)
    if result:
        return result
    result = _parse_pdf_unstructured(filepath)
    if result:
        return result
    result = _parse_pdf_pypdf(filepath)
    if result:
        return result
    return _parse_pdf_ocr(filepath)


def _parse_docx(filepath: str) -> Optional[str]:
    try:
        import docx as _docx
        doc = _docx.Document(filepath)
        parts: list[str] = []

        # Extract headers and footers from all sections
        for section in doc.sections:
            for hf in (section.header, section.footer):
                if hf is not None:
                    for p in hf.paragraphs:
                        if p.text.strip():
                            parts.append(p.text.strip())

        if parts:
            parts.append("---")

        # Extract paragraphs with heading hierarchy
        _HEADING_MAP = {
            "Heading 1": "# ", "Heading 2": "## ", "Heading 3": "### ",
            "Heading 4": "#### ", "Heading 5": "##### ", "Heading 6": "###### ",
        }
        for p in doc.paragraphs:
            if not p.text.strip():
                continue
            prefix = _HEADING_MAP.get(p.style.name, "")
            parts.append(f"{prefix}{p.text.strip()}")

        # Extract tables
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        return "\n\n".join(parts) if parts else None
    except Exception as e:
        logger.warning(f"python-docx failed for {filepath}, falling back to unstructured: {e}")
        try:
            from unstructured.partition.docx import partition_docx
            elements = partition_docx(filename=filepath)
            return "\n".join(str(el) for el in elements if str(el).strip()) or None
        except Exception as e2:
            logger.error(f"DOCX extraction failed for {filepath}: {e2}")
            return None


def _parse_doc(filepath: str) -> Optional[str]:
    """Parse legacy .doc binary format (not .docx)."""
    # Try antiword (command-line tool)
    try:
        result = subprocess.run(
            ["antiword", filepath], capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"antiword failed for {filepath}: {e}")
    # Try Unstructured
    try:
        from unstructured.partition.doc import partition_doc
        elements = partition_doc(filename=filepath)
        text = "\n".join(str(el) for el in elements if str(el).strip())
        if text:
            return text
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Unstructured partition_doc failed for {filepath}: {e}")
    logger.warning(
        f"Cannot parse legacy .doc file '{filepath}'. "
        "Install 'antiword' or 'unstructured' with doc support, "
        "or convert the file to .docx."
    )
    return None


def _parse_pptx(filepath: str) -> Optional[str]:
    """Extract text and tables from PowerPoint .pptx files."""
    try:
        from pptx import Presentation
        prs = Presentation(filepath)
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            parts = [f"--- Slide {i} ---"]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            parts.append(text)
                if shape.has_table:
                    table = shape.table
                    for row in table.rows:
                        cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if cells:
                            parts.append(" | ".join(cells))
            if len(parts) > 1:
                slides.append("\n".join(parts))
        return "\n\n".join(slides) if slides else None
    except ImportError:
        logger.warning("Library 'python-pptx' not installed. Run 'pip install python-pptx'.")
        return None
    except Exception as e:
        logger.warning(f"python-pptx failed for {filepath}, trying Unstructured: {e}")
        try:
            from unstructured.partition.pptx import partition_pptx
            elements = partition_pptx(filename=filepath)
            return "\n".join(str(el) for el in elements if str(el).strip()) or None
        except Exception as e2:
            logger.error(f"PPTX extraction failed for {filepath}: {e2}")
            return None


def _parse_eml(filepath: str) -> Optional[str]:
    """Extract headers and body from .eml email files."""
    with open(filepath, "rb") as f:
        msg = _email_mod.message_from_bytes(f.read(), policy=_email_policy.default)
    parts: list[str] = []
    for hdr in ("From", "To", "Cc", "Subject", "Date"):
        val = msg.get(hdr)
        if val:
            parts.append(f"{hdr}: {val}")
    parts.append("---")
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        content = body.get_content()
        if body.get_content_type() == "text/html":
            content = re.sub(r'<[^>]+>', '', content)
        if content.strip():
            parts.append(content.strip())
    attachments = [att.get_filename() for att in msg.iter_attachments() if att.get_filename()]
    if attachments:
        parts.append(f"Attachments: {', '.join(attachments)}")
    return "\n\n".join(parts) if len(parts) > 1 else None


def _parse_msg(filepath: str) -> Optional[str]:
    """Extract headers and body from Outlook .msg files."""
    try:
        import extract_msg
        msg = extract_msg.Message(filepath)
        parts: list[str] = []
        for hdr, val in [("From", msg.sender), ("To", msg.to), ("Cc", msg.cc),
                         ("Subject", msg.subject), ("Date", msg.date)]:
            if val:
                parts.append(f"{hdr}: {val}")
        parts.append("---")
        if msg.body:
            parts.append(msg.body.strip())
        msg.close()
        return "\n\n".join(parts) if len(parts) > 1 else None
    except ImportError:
        logger.warning("Library 'extract-msg' not installed. Run 'pip install extract-msg'.")
        return None
    except Exception as e:
        logger.error(f"MSG extraction failed for {filepath}: {e}")
        return None


def extract_text_from_file(filepath: str) -> Optional[str]:
    if not os.path.exists(filepath):
        logger.error(f"File not found at specified path: {filepath}")
        return None

    ext = os.path.splitext(filepath)[1].lower()
    loaders = {
        '.txt':  _read_text_file,
        '.md':   _read_text_file,
        '.json': _read_json_file,
        '.csv':  _read_csv,
        '.xlsx': _xlsx_to_text,
        '.xls':  _parse_xls,
        '.xml':  _xml_to_text,
        '.pdf':  _parse_pdf,
        '.docx': _parse_docx,
        '.doc':  _parse_doc,
        '.pptx': _parse_pptx,
        '.eml':  _parse_eml,
        '.msg':  _parse_msg,
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
    return _detect_and_read(filepath)


def _read_json_file(filepath: str) -> str:
    text = _detect_and_read(filepath)
    data = json.loads(text)
    return _json_to_text(data)


def _read_csv(filepath: str) -> str:
    text = _detect_and_read(filepath)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        logger.warning(f"CSV dialect detection failed for {filepath}, using default comma delimiter.")
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    lines = [" | ".join(cell for cell in row if cell.strip()) for row in reader]
    return "\n".join(line for line in lines if line)


def _xlsx_to_text(filepath: str) -> str:
    """
    Convert an Excel file (.xlsx) to structured text with semantic context.
    Handles merged cells, configurable row limit, and formula error filtering.
    """
    try:
        import openpyxl
        # read_only=False is required to access merged_cells information
        workbook = openpyxl.load_workbook(filepath, data_only=True)
        lines: list[str] = []
        filename = os.path.basename(filepath)

        # Semantic header — makes the file findable by search
        sheet_info = []
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            max_row = min(sheet.max_row or 0, _MAX_XLSX_ROWS)
            if sheet.max_row and sheet.max_row > _MAX_XLSX_ROWS:
                logger.warning(
                    f"Sheet '{sheet_name}' in '{filename}' truncated: "
                    f"{sheet.max_row} rows, limit {_MAX_XLSX_ROWS}"
                )
            rows = list(sheet.iter_rows(max_row=max_row))
            if rows:
                headers = [str(cell.value or "") for cell in rows[0]]
                n_rows = max(0, len(rows) - 1)
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
            max_row = min(sheet.max_row or 0, _MAX_XLSX_ROWS)

            # Build merged cell value map: propagate top-left value to all cells in range
            merged_values: dict[tuple[int, int], Any] = {}
            for merge_range in sheet.merged_cells.ranges:
                top_left_value = sheet.cell(merge_range.min_row, merge_range.min_col).value
                for row_idx in range(merge_range.min_row, merge_range.max_row + 1):
                    for col_idx in range(merge_range.min_col, merge_range.max_col + 1):
                        merged_values[(row_idx, col_idx)] = top_left_value

            rows = list(sheet.iter_rows(max_row=max_row))
            if not rows:
                continue
            headers = [str(cell.value or "") for cell in rows[0]]

            if len(workbook.sheetnames) > 1:
                lines.append(f"\n=== Sheet: {sheet_name} ===")

            for row in rows[1:]:
                parts = []
                for i, cell in enumerate(row):
                    value = merged_values.get((cell.row, cell.column), cell.value)
                    if value is None:
                        continue
                    str_val = str(value)
                    if str_val in _FORMULA_ERRORS:
                        continue
                    header = headers[i] if i < len(headers) else f"Col{i}"
                    parts.append(f"{header}: {str_val}")
                if parts:
                    lines.append(" | ".join(parts))

        workbook.close()
        return "\n".join(lines)
    except ImportError:
        logger.warning("Library 'openpyxl' not installed.")
        return ""


def _parse_xls(filepath: str) -> Optional[str]:
    """Parse legacy .xls Excel files via xlrd."""
    try:
        import xlrd
        workbook = xlrd.open_workbook(filepath)
        lines: list[str] = []
        filename = os.path.basename(filepath)

        lines.append(f"[FILE: {filename}]")
        lines.append(
            f"This file contains {workbook.nsheets} sheet(s): "
            f"{', '.join(workbook.sheet_names())}."
        )
        lines.append("---")

        for sheet in workbook.sheets():
            if sheet.nrows == 0:
                continue
            headers = [str(sheet.cell_value(0, c) or "") for c in range(sheet.ncols)]
            if workbook.nsheets > 1:
                lines.append(f"\n=== Sheet: {sheet.name} ===")

            max_row = min(sheet.nrows, _MAX_XLSX_ROWS)
            if sheet.nrows > _MAX_XLSX_ROWS:
                logger.warning(
                    f"Sheet '{sheet.name}' in '{filename}' truncated: "
                    f"{sheet.nrows} rows, limit {_MAX_XLSX_ROWS}"
                )
            for r in range(1, max_row):
                parts = []
                for c in range(sheet.ncols):
                    value = sheet.cell_value(r, c)
                    if value in (None, ""):
                        continue
                    str_val = str(value)
                    if str_val in _FORMULA_ERRORS:
                        continue
                    header = headers[c] if c < len(headers) else f"Col{c}"
                    parts.append(f"{header}: {str_val}")
                if parts:
                    lines.append(" | ".join(parts))

        return "\n".join(lines) if lines else None
    except ImportError:
        logger.warning("Library 'xlrd' not installed. Run 'pip install xlrd'.")
        return None
    except Exception as e:
        logger.error(f"XLS extraction failed for {filepath}: {e}")
        return None


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
        pass
    except Exception as e:
        logger.warning(f"Unstructured failed for XML {filepath}: {e}")
    # Fallback: defusedxml (XXE-safe) instead of stdlib xml.etree.ElementTree
    # WHY: stdlib xml.etree is vulnerable to XML External Entity (XXE) attacks
    # and billion-laughs DoS. User-uploaded XML files must be parsed with
    # defusedxml which blocks external entity resolution and entity expansion.
    try:
        text = _detect_and_read(filepath)
        try:
            from defusedxml import ElementTree as DefusedET
            root = DefusedET.fromstring(text)
        except ImportError:
            # defusedxml not installed — fall back to stdlib but log a warning.
            # This should not happen in production (defusedxml is in requirements).
            logger.warning("defusedxml not installed, falling back to stdlib xml.etree (XXE-vulnerable). "
                           "Install with: pip install defusedxml")
            root = ET.fromstring(text)
        parts = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if elem.text and elem.text.strip():
                parts.append(f"{tag}: {elem.text.strip()}")
        return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.error(f"XML extraction failed for {filepath}: {e}")
        return ""
