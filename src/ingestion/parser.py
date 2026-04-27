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
from typing import Optional, Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")


def _parse_pdf_llamaparse(filepath: str) -> Optional[str]:
    """
    Tente d'extraire le texte d'un PDF en utilisant l'API LlamaParse.

    Args:
        filepath (str): Chemin vers le fichier PDF.

    Returns:
        Optional[str]: Texte extrait au format Markdown, ou None si l'API est indisponible ou en cas d'erreur.
    """
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
    """
    Nettoie et normalise le texte brut extrait des documents.
    Supprime le HTML, les en-têtes Markdown, normalise les variables template et les espaces.

    Args:
        raw_text (str): Le texte brut à nettoyer.

    Returns:
        str: Le texte nettoyé et formaté.
    """
    if not raw_text:
        return ""

    # Suppression des balises HTML
    text = re.sub(r'<[^>]+>', '', raw_text)
    
    # Suppression des symboles de titres Markdown (#)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Normalisation des variables template (%VAR_NAME% → VAR_NAME)
    text = re.sub(r'%[A-Z_0-9]+%', lambda m: m.group(0).replace('%', ''), text)

    # Normalisation des espaces et gestion des paragraphes
    paragraphs = re.split(r'\n\s*\n', text)
    cleaned_paragraphs = [" ".join(p.split()) for p in paragraphs if p.strip()]
    return "\n\n".join(cleaned_paragraphs)


def _parse_pdf_pymupdf(filepath: str) -> Optional[str]:
    """
    Moteur de parsing PDF utilisant PyMuPDF (fitz). Très fiable, rapide,
    et ne nécessite aucune dépendance système (contrairement à poppler).

    Args:
        filepath (str): Chemin vers le fichier PDF.

    Returns:
        Optional[str]: Texte extrait, ou None en cas d'échec.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        if not pages:
            logger.warning(f"PyMuPDF: aucune texte extrait de {filepath} (PDF possibly image-only).")
            return None
        return "\n".join(pages)
    except ImportError:
        logger.warning("Bibliothèque 'pymupdf' non installée. Exécutez 'pip install pymupdf'.")
        return None
    except Exception as e:
        logger.warning(f"PyMuPDF a échoué pour {filepath} : {e}")
        return None


def _parse_pdf_unstructured(filepath: str) -> Optional[str]:
    """
    Moteur de secours pour le parsing PDF utilisant la bibliothèque Unstructured.

    Args:
        filepath (str): Chemin vers le fichier PDF.

    Returns:
        Optional[str]: Texte extrait, ou None en cas d'échec.
    """
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


def _parse_pdf(filepath: str) -> Optional[str]:
    """
    Orchestre le parsing PDF avec une chaîne de fallback :
    1. LlamaParse (API cloud, meilleur qualité)
    2. PyMuPDF (local, rapide, fiable)
    3. Unstructured (local, bon pour les PDF complexes)

    Args:
        filepath (str): Chemin vers le fichier PDF.

    Returns:
        Optional[str]: Texte complet extrait du PDF.
    """
    # 1. LlamaParse (API cloud — nécessite LLAMA_CLOUD_API_KEY)
    result = _parse_pdf_llamaparse(filepath)
    if result:
        return result

    # 2. PyMuPDF — fallback local rapide et très fiable
    result = _parse_pdf_pymupdf(filepath)
    if result:
        return result

    # 3. Unstructured — dernier recours
    return _parse_pdf_unstructured(filepath)


def extract_text_from_file(filepath: str) -> Optional[str]:
    """
    Fonction principale pour extraire le texte d'un fichier en fonction de son extension.

    Args:
        filepath (str): Chemin vers le fichier à traiter.

    Returns:
        Optional[str]: Le texte brut extrait du fichier, ou None si le format n'est pas supporté ou si le fichier est introuvable.
    """
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
    """Lit un fichier texte simple ou Markdown."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _read_json_file(filepath: str) -> str:
    """Lit et convertit un fichier JSON en texte structuré."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return _json_to_text(data)


def _read_csv(filepath: str) -> str:
    """Extrait les données d'un fichier CSV en tentant de détecter son dialecte.
    Retourne le texte brut complet pour le chunking tabulaire."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return f.read()


def read_csv_raw(filepath: str) -> Tuple[List[str], List[List[str]]]:
    """Parse un CSV et retourne (headers, data_rows) pour le chunking tabulaire.

    Args:
        filepath: Chemin vers le fichier CSV.

    Returns:
        Tuple de (headers, data_rows) où headers est la liste des noms de colonnes
        et data_rows est la liste des lignes de données (chaque ligne = liste de str).
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            # Fallback : détection par séparateur commun
            if '\t' in sample[:1000]:
                dialect = csv.excel_tab
            elif ';' in sample[:1000]:
                class SemiColonDialect(csv.excel):
                    delimiter = ';'
                dialect = SemiColonDialect()
            else:
                dialect = csv.excel
        reader = csv.reader(f, dialect)
        rows = list(reader)

    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    data_rows = [[cell.strip() for cell in row] for row in rows[1:]]
    return headers, data_rows


def _xlsx_to_text(filepath: str) -> str:
    """Convertit un fichier Excel en texte plat (fallback pour les anciens appels).
    Préférer read_xlsx_sheets() pour le chunking tabulaire."""
    sheets = read_xlsx_sheets(filepath)
    if not sheets:
        return ""
    all_lines = []
    for sheet_name, headers, data_rows in sheets:
        for row in data_rows:
            parties = [
                f"{headers[i] if i < len(headers) else f'Col{i}'}: {cell}"
                for i, cell in enumerate(row) if cell is not None and str(cell).strip()
            ]
            if parties:
                all_lines.append(" | ".join(parties))
    return "\n".join(all_lines)


def read_xlsx_sheets(filepath: str) -> List[Tuple[str, List[str], List[List[Optional[str]]]]]:
    """Parse un fichier XLSX et retourne les données structurées par feuille.

    Returns:
        Liste de tuples (sheet_name, headers, data_rows) pour chaque feuille.
        headers: liste des noms de colonnes.
        data_rows: liste de lignes (chaque ligne = liste de valeurs str ou None).
    """
    try:
        import openpyxl
        classeur = openpyxl.load_workbook(filepath, read_only=True)
        sheets = []

        for nom_feuille in classeur.sheetnames:
            sheet = classeur[nom_feuille]
            rows = list(sheet.rows)
            if not rows:
                continue
            headers = [str(cell.value or "").strip() for cell in rows[0]]
            data_rows = []
            for row in rows[1:]:
                data_rows.append([cell.value for cell in row])
            sheets.append((nom_feuille, headers, data_rows))

        classeur.close()
        return sheets
    except ImportError:
        logger.warning("Bibliothèque 'openpyxl' non installée.")
        return []
    except Exception as e:
        logger.error(f"Erreur lors de la lecture XLSX {filepath} : {e}")
        return []


def _json_to_text(data: Any, niveau: int = 0) -> str:
    """
    Convertit récursivement un objet Python (issu d'un JSON) en texte lisible avec indentation.

    Args:
        data (Any): L'objet à convertir (dict, list, str, etc.).
        niveau (int): Niveau d'indentation actuel.

    Returns:
        str: Représentation textuelle de l'objet.
    """
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
    """
    Extrait le texte d'un fichier XML en utilisant Unstructured pour gérer la hiérarchie.

    Args:
        filepath (str): Chemin vers le fichier XML.

    Returns:
        str: Texte extrait ou chaîne vide en cas d'erreur.
    """
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
