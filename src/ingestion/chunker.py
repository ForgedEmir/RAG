"""Chunking de documents texte et tabulaires.
- Texte classique : RecursiveCharacterTextSplitter de LangChain.
- CSV/XLSX : chunking tabulaire (1 ligne = 1 chunk avec headers répétés).
"""
import csv
import io
import logging
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=_SEPARATORS
)

# Limites de sécurité pour le chunking tabulaire
_TABULAR_MAX_ROWS_PER_CHUNK = 5       # Lignes de données max par chunk
_TABULAR_SUMMARY_EVERY_N_ROWS = 50    # Génère un chunk résumé tous les N lignes
_TABULAR_MAX_CHUNKS = 2000            # Limite absolue pour éviter l'explosion mémoire


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Chunking classique pour du texte narratif (MD, TXT, JSON, XML, PDF...)."""
    if not isinstance(text, str) or not text.strip():
        return []
    if chunk_size == CHUNK_SIZE and overlap == CHUNK_OVERLAP:
        return _DEFAULT_SPLITTER.split_text(text)
    # Évite les erreurs si overlap >= chunk_size
    safe_overlap = min(overlap, chunk_size // 5) if overlap >= chunk_size else overlap
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=safe_overlap, separators=_SEPARATORS
    ).split_text(text)


def split_tabular_csv(
    csv_text: str,
    delimiter: str = ";",
    filename: str = "",
) -> List[str]:
    """Chunking tabulaire pour les fichiers CSV.

    Stratégie production-ready :
    1. Chaque groupe de _TABULAR_MAX_ROWS_PER_CHUNK lignes devient un chunk.
    2. Les en-têtes (noms de colonnes) sont répétés dans CHAQUE chunk pour
       garantir que le contexte colonne est toujours présent, même si le chunk
       est récupéré isolément lors de la recherche.
    3. Un chunk résumé est inséré tous les _TABULAR_SUMMARY_EVERY_N_ROWS lignes,
       contenant les statistiques du fichier (nb lignes, colonnes, plage de valeurs)
       pour aider le LLM à répondre aux questions agrégées.
    4. Le premier chunk est un "schema chunk" qui liste les colonnes et le nombre
       total de lignes — idéal pour les requêtes méta ("combien de lignes?").

    Args:
        csv_text: Le contenu texte brut du CSV.
        delimiter: Le séparateur du CSV (';' ou ',').
        filename: Nom du fichier (pour les messages de log).

    Returns:
        Liste de chunks textuels prêts à être indexés.
    """
    if not csv_text or not csv_text.strip():
        return []

    # Auto-détection du délimiteur si nécessaire
    if delimiter not in (",", ";", "\t", "|"):
        sniffer_sample = csv_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sniffer_sample)
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

    try:
        reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
        rows = list(reader)
    except Exception as e:
        logger.warning(f"Échec du parsing CSV tabulaire pour '{filename}' : {e}. Fallback texte plat.")
        return split_into_chunks(csv_text)

    if not rows:
        return []

    # Séparer headers et données
    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    total_data_rows = len(data_rows)

    if not headers or total_data_rows == 0:
        return split_into_chunks(csv_text)

    # Limite de sécurité
    if total_data_rows > _TABULAR_MAX_CHUNKS * _TABULAR_MAX_ROWS_PER_CHUNK:
        logger.warning(
            f"CSV '{filename}' très volumineux ({total_data_rows} lignes). "
            f"Limité à {_TABULAR_MAX_CHUNKS} chunks."
        )
        data_rows = data_rows[:_TABULAR_MAX_CHUNKS * _TABULAR_MAX_ROWS_PER_CHUNK]
        total_data_rows = len(data_rows)

    header_line = " | ".join(headers)
    chunks: List[str] = []

    # ── Chunk 0 : Schema (métadonnées du fichier) ──────────────────────────
    schema_chunk = (
        f"[Schéma du fichier {filename}]\n"
        f"Colonnes ({len(headers)}) : {header_line}\n"
        f"Nombre total de lignes de données : {total_data_rows}\n"
    )
    chunks.append(schema_chunk)

    # ── Chunks de données : _TABULAR_MAX_ROWS_PER_CHUNK lignes par chunk ────
    for batch_start in range(0, total_data_rows, _TABULAR_MAX_ROWS_PER_CHUNK):
        batch = data_rows[batch_start:batch_start + _TABULAR_MAX_ROWS_PER_CHUNK]
        batch_lines: List[str] = []

        for row_idx, row in enumerate(batch):
            global_idx = batch_start + row_idx + 1  # 1-indexed pour lisibilité
            # Associer chaque cellule à son header
            cell_parts: List[str] = []
            for col_idx, cell in enumerate(row):
                col_name = headers[col_idx] if col_idx < len(headers) else f"Colonne_{col_idx + 1}"
                cell_value = cell.strip() if cell else ""
                if cell_value:
                    cell_parts.append(f"{col_name}: {cell_value}")
            if cell_parts:
                batch_lines.append(f"Ligne {global_idx} — " + " | ".join(cell_parts))

        if not batch_lines:
            continue

        # Préfixer avec les headers pour que le chunk soit auto-suffisant
        chunk_text = (
            f"[Fichier: {filename} — Colonnes: {header_line} — Lignes {batch_start + 1} à {batch_start + len(batch)}]\n"
            + "\n".join(batch_lines)
        )
        chunks.append(chunk_text)

        # ── Chunk résumé périodique ─────────────────────────────────────────
        row_end = batch_start + len(batch)
        if row_end % _TABULAR_SUMMARY_EVERY_N_ROWS == 0 and row_end < total_data_rows:
            summary = _build_tabular_summary(headers, data_rows[:row_end], filename, row_end)
            if summary:
                chunks.append(summary)

    # ── Chunk résumé final (si assez de données) ────────────────────────────
    if total_data_rows > _TABULAR_SUMMARY_EVERY_N_ROWS:
        final_summary = _build_tabular_summary(headers, data_rows, filename, total_data_rows)
        if final_summary:
            chunks.append(final_summary)

    logger.info(
        f"Chunking tabulaire CSV '{filename}': {total_data_rows} lignes → {len(chunks)} chunks "
        f"(schema: 1, données: {len(chunks) - 2 - (1 if total_data_rows > _TABULAR_SUMMARY_EVERY_N_ROWS else 0)}, "
        f"résumés: {1 + (1 if total_data_rows > _TABULAR_SUMMARY_EVERY_N_ROWS else 0)})"
    )
    return chunks


def split_tabular_xlsx(
    rows_data: List[List[Optional[str]]],
    headers: List[str],
    filename: str = "",
    sheet_name: str = "",
) -> List[str]:
    """Chunking tabulaire pour les fichiers XLSX.

    Même stratégie que split_tabular_csv mais reçoit directement les données
    déjà parsées par openpyxl (pas besoin de re-parser).

    Args:
        rows_data: Liste de listes de valeurs cellulaires (sans la ligne d'en-tête).
        headers: Liste des noms de colonnes.
        filename: Nom du fichier.
        sheet_name: Nom de la feuille Excel.

    Returns:
        Liste de chunks textuels prêts à être indexés.
    """
    if not headers or not rows_data:
        return []

    total_data_rows = len(rows_data)

    # Limite de sécurité
    if total_data_rows > _TABULAR_MAX_CHUNKS * _TABULAR_MAX_ROWS_PER_CHUNK:
        logger.warning(
            f"XLSX '{filename}' très volumineux ({total_data_rows} lignes). "
            f"Limité à {_TABULAR_MAX_CHUNKS} chunks."
        )
        rows_data = rows_data[:_TABULAR_MAX_CHUNKS * _TABULAR_MAX_ROWS_PER_CHUNK]
        total_data_rows = len(rows_data)

    header_line = " | ".join(headers)
    sheet_label = f" (feuille: {sheet_name})" if sheet_name else ""
    chunks: List[str] = []

    # ── Chunk 0 : Schema ────────────────────────────────────────────────────
    schema_chunk = (
        f"[Schéma du fichier {filename}{sheet_label}]\n"
        f"Colonnes ({len(headers)}) : {header_line}\n"
        f"Nombre total de lignes de données : {total_data_rows}\n"
    )
    chunks.append(schema_chunk)

    # ── Chunks de données ───────────────────────────────────────────────────
    for batch_start in range(0, total_data_rows, _TABULAR_MAX_ROWS_PER_CHUNK):
        batch = rows_data[batch_start:batch_start + _TABULAR_MAX_ROWS_PER_CHUNK]
        batch_lines: List[str] = []

        for row_idx, row in enumerate(batch):
            global_idx = batch_start + row_idx + 1
            cell_parts: List[str] = []
            for col_idx, cell_value in enumerate(row):
                col_name = headers[col_idx] if col_idx < len(headers) else f"Colonne_{col_idx + 1}"
                str_value = str(cell_value).strip() if cell_value is not None else ""
                if str_value:
                    cell_parts.append(f"{col_name}: {str_value}")
            if cell_parts:
                batch_lines.append(f"Ligne {global_idx} — " + " | ".join(cell_parts))

        if not batch_lines:
            continue

        chunk_text = (
            f"[Fichier: {filename}{sheet_label} — Colonnes: {header_line} — "
            f"Lignes {batch_start + 1} à {batch_start + len(batch)}]\n"
            + "\n".join(batch_lines)
        )
        chunks.append(chunk_text)

        # Résumé périodique
        row_end = batch_start + len(batch)
        if row_end % _TABULAR_SUMMARY_EVERY_N_ROWS == 0 and row_end < total_data_rows:
            summary = _build_tabular_summary(headers, rows_data[:row_end], filename, row_end, sheet_name)
            if summary:
                chunks.append(summary)

    # Résumé final
    if total_data_rows > _TABULAR_SUMMARY_EVERY_N_ROWS:
        final_summary = _build_tabular_summary(headers, rows_data, filename, total_data_rows, sheet_name)
        if final_summary:
            chunks.append(final_summary)

    logger.info(
        f"Chunking tabulaire XLSX '{filename}'{sheet_label}: {total_data_rows} lignes → {len(chunks)} chunks"
    )
    return chunks


def _build_tabular_summary(
    headers: List[str],
    data_rows: List[list],
    filename: str,
    num_rows: int,
    sheet_name: str = "",
) -> Optional[str]:
    """Génère un chunk résumé avec des statistiques basiques sur les données.

    WHY: Les questions agrégées ("combien y a-t-il de...?", "quelle est la valeur max?")
    sont impossibles à répondre si le LLM ne voit que quelques lignes. Un chunk résumé
    avec les valeurs uniques par colonne et le compte aide énormément.
    """
    sheet_label = f" (feuille: {sheet_name})" if sheet_name else ""
    lines: List[str] = [f"[Résumé statistique — {filename}{sheet_label} — {num_rows} lignes]"]

    for col_idx, header in enumerate(headers):
        values: List[str] = []
        for row in data_rows:
            if col_idx < len(row):
                val = str(row[col_idx]).strip() if row[col_idx] is not None else ""
                if val:
                    values.append(val)

        if not values:
            continue

        unique_values = set(values)
        # Si moins de 20 valeurs uniques, on les liste
        if len(unique_values) <= 20:
            sorted_vals = sorted(unique_values)
            lines.append(f"{header} ({len(unique_values)} valeurs uniques) : {', '.join(sorted_vals)}")
        else:
            lines.append(f"{header} : {len(values)} valeurs, {len(unique_values)} valeurs uniques (échantillon : {', '.join(list(unique_values)[:10])}...)")

    return "\n".join(lines) if len(lines) > 1 else None
