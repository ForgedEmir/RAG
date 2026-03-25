"""
Extraction et nettoyage de texte pour tous les formats supportés :
.md, .txt, .json, .csv, .xlsx, .xml, .pdf

PDF : utilise LlamaParse si LLAMA_CLOUD_API_KEY est défini, sinon Unstructured.
"""
import os
import re
import csv
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")


def _parse_pdf_llamaparse(filepath: str) -> Optional[str]:
    """Parse un PDF complexe via LlamaParse. Retourne None si indisponible."""
    if not _LLAMA_API_KEY:
        return None
    try:
        from llama_parse import LlamaParse
        parser = LlamaParse(api_key=_LLAMA_API_KEY, result_type="markdown")
        documents = parser.load_data(filepath)
        return "\n\n".join(doc.text for doc in documents if doc.text)
    except ImportError:
        logger.warning("llama-parse non installé — pip install llama-parse")
        return None
    except Exception as e:
        logger.warning(f"LlamaParse échoué pour {filepath}, fallback Unstructured : {e}")
        return None


def clean_text(raw_text: str) -> str:
    """Nettoie un texte brut : supprime HTML, headers Markdown,
    remplace les variables de jeu, normalise les espaces.
    """
    if not raw_text:
        return ""

    text = re.sub(r'<[^>]+>', '', raw_text)                    # HTML
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE) # Titres Markdown
    text = text.replace('%PLAYER_NAME%', 'le joueur')          # Variables de jeu
    text = re.sub(r'%[A-Z_0-9]+%', lambda m: m.group(0).replace('%', ''), text)

    # Normalise les espaces dans chaque paragraphe
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [" ".join(p.split()) for p in paragraphs if p.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_file(filepath: str) -> Optional[str]:
    """Lit un fichier selon son extension et retourne son contenu en texte brut."""
    if not os.path.exists(filepath):
        logger.error(f"Fichier introuvable : {filepath}")
        return None

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    try:
        if ext == '.pdf':
            text = _parse_pdf_llamaparse(filepath)
            if text:
                logger.info(f"PDF parsé via LlamaParse : {filepath}")
                return text
            logger.info(f"PDF sans clé LlamaParse, fallback Unstructured : {filepath}")
            return None

        if ext in ('.txt', '.md'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()

        elif ext == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                return _json_to_text(json.load(f))

        elif ext == '.csv':
            with open(filepath, 'r', encoding='utf-8') as f:
                dialect = csv.Sniffer().sniff(f.read(8192))
                f.seek(0)
                lignes = [
                    " ".join(cell for cell in row if cell.strip())
                    for row in csv.reader(f, dialect)
                ]
                return "\n".join(l for l in lignes if l)

        elif ext == '.xlsx':
            return _xlsx_to_text(filepath)

        elif ext == '.xml':
            return _xml_to_text(filepath)

        else:
            logger.warning(f"Format non supporté : {ext}")
            return None

    except Exception as e:
        logger.error(f"Erreur en lisant {filepath} : {e}")
        return None


def _xlsx_to_text(filepath: str) -> str:
    """Excel → texte : 'Colonne: Valeur | Colonne: Valeur'"""
    import openpyxl
    classeur = openpyxl.load_workbook(filepath, read_only=True)
    lignes = []

    for nom_feuille in classeur.sheetnames:
        sheet = classeur[nom_feuille]
        rows = list(sheet.rows)
        if not rows:
            continue
        headers = [str(cell.value or "") for cell in rows[0]]
        for row in rows[1:]:
            parties = [
                f"{headers[i] if i < len(headers) else f'Col{i}'}: {cell.value}"
                for i, cell in enumerate(row) if cell.value is not None
            ]
            if parties:
                lignes.append(" | ".join(parties))

    classeur.close()
    return "\n".join(lignes)


def _json_to_text(data, niveau: int = 0) -> str:
    """Convertit récursivement un objet JSON en texte lisible."""
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

    return "\n".join(l for l in lignes if l)


def _xml_to_text(filepath: str) -> str:
    """Extrait tout le texte d'un fichier XML (ignore les balises)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(filepath).getroot()
        lignes = [elem.text.strip() for elem in root.iter() if elem.text and elem.text.strip()]
        return "\n".join(lignes)
    except ET.ParseError as e:
        logger.error(f"XML corrompu {filepath} : {e}")
        return ""
