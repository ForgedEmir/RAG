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
from xml.etree import ElementTree

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


def _parse_pdf_unstructured(filepath: str) -> Optional[str]:
    """Fallback PDF via unstructured si LlamaParse indisponible."""
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=filepath)
        return "\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        logger.warning("unstructured non installé — pip install unstructured")
        return None
    except Exception as e:
        logger.error(f"unstructured échoué pour {filepath} : {e}")
        return None


def _parse_pdf(filepath: str) -> Optional[str]:
    """Parse un PDF : LlamaParse si disponible, sinon unstructured."""
    result = _parse_pdf_llamaparse(filepath)
    if result:
        return result
    return _parse_pdf_unstructured(filepath)


def extract_text_from_file(filepath: str) -> Optional[str]:
    """Lit un fichier selon son extension et retourne son contenu en texte brut."""
    if not isinstance(filepath, str):
        return None

    if not os.path.exists(filepath):
        logger.error(f"Fichier introuvable : {filepath}")
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
    }
    loader = loaders.get(ext)
    if not loader:
        logger.warning(f"Format non supporté : {ext}")
        return None
    try:
        return loader(filepath)
    except Exception as e:
        logger.error(f"Erreur en lisant {filepath} : {e}")
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
        lines = [" ".join(c for c in row if c.strip()) for row in csv.reader(f, dialect)]
        return "\n".join(l for l in lines if l)


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
    """Extrait uniquement les nœuds texte d'un document XML bien formé."""
    try:
        root = ElementTree.parse(filepath).getroot()
        # ElementTree valide le XML et n'inclut ni balises ni attributs dans itertext().
        return "\n".join(text.strip() for text in root.itertext() if text.strip())
    except (ElementTree.ParseError, OSError) as e:
        logger.error(f"Erreur XML {filepath} : {e}")
        return ""
