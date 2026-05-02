"""
Module de parsing de documents pour le système RAG.
Supporte les formats : .md, .txt, .json, .csv, .xlsx, .xml, .pdf.
Utilise LlamaParse pour les PDF complexes et Unstructured en repli.
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
        logger.warning("Bibliothèque 'llama-parse' non installée. Exécutez 'pip install llama-parse'.")
        return None
    except Exception as e:
        logger.warning(f"LlamaParse a échoué pour {filepath}, passage au moteur Unstructured : {e}")
        return None


def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = text.replace('%PLAYER_NAME%', 'le joueur')
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
        logger.warning("Bibliothèque 'unstructured' non installée. Exécutez 'pip install unstructured'.")
        return None
    except Exception as e:
        logger.error(f"Échec de l'extraction Unstructured pour {filepath} : {e}")
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
        logger.warning(f"pypdf a échoué pour {filepath} : {e}")
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
        logger.warning(f"python-docx a échoué pour {filepath}, fallback unstructured : {e}")
        try:
            from unstructured.partition.docx import partition_docx
            elements = partition_docx(filename=filepath)
            return "\n".join(str(el) for el in elements if str(el).strip()) or None
        except Exception as e2:
            logger.error(f"Échec extraction DOCX pour {filepath} : {e2}")
            return None


def extract_text_from_file(filepath: str) -> Optional[str]:
    if not os.path.exists(filepath):
        logger.error(f"Fichier introuvable au chemin spécifié : {filepath}")
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
        logger.warning(f"Format de fichier non supporté : {ext}")
        return None

    try:
        return loader(filepath)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier {filepath} : {e}")
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
    Convertit un fichier Excel (.xlsx) en texte structuré avec contexte sémantique.
    Ajoute un en-tête décrivant le fichier, les feuilles et les colonnes
    pour que le contenu soit trouvable par recherche vectorielle et BM25.

    Exemple de sortie :
        [FICHIER: base_prospect_V2.xlsx]
        Ce fichier contient 3 feuilles : Prospects, Statistiques, Notes.
        Feuille 'Prospects' (120 lignes) — Colonnes: Nom, Âge, Ville, Email, Téléphone
        ---
        Nom: Jean | Âge: 35 | Ville: Paris | Email: jean@test.com
        Nom: Marie | Âge: 28 | Ville: Lyon | Email: marie@test.com
    """
    try:
        import openpyxl
        classeur = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        lignes = []

        filename = os.path.basename(filepath)
        nom_sans_ext = os.path.splitext(filename)[0]

        # En-tête sémantique — rend le fichier trouvable par recherche
        sheet_info = []
        total_rows = 0
        for nom_feuille in classeur.sheetnames:
            sheet = classeur[nom_feuille]
            rows = list(sheet.iter_rows(max_row=min(sheet.max_row, 2000)))
            if rows:
                headers = [str(cell.value or "") for cell in rows[0]]
                n_rows = max(0, len(rows) - 1)
                total_rows += n_rows
                sheet_info.append(
                    f"Feuille '{nom_feuille}' ({n_rows} lignes)"
                    f" — Colonnes: {', '.join(h for h in headers if h)}"
                )

        lignes.append(f"[FICHIER: {filename}]")
        lignes.append(
            f"Ce fichier contient {len(classeur.sheetnames)} feuille(s) : "
            f"{', '.join(classeur.sheetnames)}."
        )
        for info in sheet_info:
            lignes.append(info)
        lignes.append("---")

        for nom_feuille in classeur.sheetnames:
            sheet = classeur[nom_feuille]
            rows = list(sheet.iter_rows(max_row=min(sheet.max_row, 2000)))
            if not rows:
                continue
            headers = [str(cell.value or "") for cell in rows[0]]

            # Ligne d'en-tête avec noms de colonnes explicites
            if len(classeur.sheetnames) > 1:
                lignes.append(f"\n=== Feuille: {nom_feuille} ===")

            for row in rows[1:]:
                parties = [
                    f"{headers[i] if i < len(headers) else f'Col{i}'}: {cell.value}"
                    for i, cell in enumerate(row) if cell.value is not None
                ]
                if parties:
                    lignes.append(" | ".join(parties))

        classeur.close()
        return "\n".join(lignes)
    except ImportError:
        logger.warning("Bibliothèque 'openpyxl' non installée.")
        return ""


def _json_to_text(data: Any, niveau: int = 0) -> str:
    lignes = []
    indent = "  " * niveau

    if isinstance(data, dict):
        for cle, valeur in data.items():
            if isinstance(valeur, (dict, list)):
                lignes.append(f"{indent}{cle}:")
                lignes.append(_json_to_text(valeur, niveau + 1))
            else:
                lignes.append(f"{indent}{cle}: {valeur}")

    elif isinstance(data, list):
        for element in data:
            lignes.append(_json_to_text(element, niveau))
            lignes.append(f"{indent}---")

    else:
        lignes.append(f"{indent}{data}")

    return "\n".join(line for line in lignes if line)


def _xml_to_text(filepath: str) -> str:
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("Bibliothèque 'unstructured' non installée.")
        return ""
    except Exception as e:
        logger.error(f"Erreur lors du traitement XML de {filepath} : {e}")
        return ""
