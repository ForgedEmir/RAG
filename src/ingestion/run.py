import os
import chromadb
import json
from typing import Dict, List
from src.ingestion.parser import lire_fichiers_md
from src.ingestion.chunker import decouper_en_chunks
from src.ingestion.loader import stocker_dans_chromadb


def indexer_donnees(force_reindex: bool = False, auto_detect_changes: bool = True) -> bool:
    """
    Indexe les données dans ChromaDB si elles ne sont pas déjà indexées.
    
    Args:
        force_reindex: Si True, force la réindexation complète de tous les fichiers
        auto_detect_changes: Si True, détecte les nouveaux fichiers, modifications et suppressions
    
    Returns:
        True si l'indexation a été effectuée, False si elle était déjà faite
    """
    # Chemin de la base de données
    base_dir = os.path.dirname(__file__)
    db_path = os.path.join(base_dir, "chroma_db")
    data_path = os.path.normpath(os.path.join(base_dir, "..", "..", "data", "sample"))
    metadata_path = os.path.join(db_path, "files_metadata.json")
    
    # Lister les fichiers .md actuels avec leurs dates de modification
    fichiers_actuels = {}
    for f in os.listdir(data_path):
        if f.endswith(".md"):
            chemin = os.path.join(data_path, f)
            mtime = os.path.getmtime(chemin)
            fichiers_actuels[f] = mtime
    
    # Vérifier si l'indexation existe déjà
    if not force_reindex and os.path.exists(db_path):
        try:
            client = chromadb.PersistentClient(path=db_path)
            collection = client.get_collection(name="lore")
            count = collection.count()
            
            if count > 0:
                # Vérifier les changements
                if auto_detect_changes:
                    # Récupérer les fichiers déjà indexés
                    all_data = collection.get()
                    fichiers_indexes = set()
                    if all_data and 'metadatas' in all_data:
                        for metadata in all_data['metadatas']:
                            if metadata and 'fichier' in metadata:
                                fichiers_indexes.add(metadata['fichier'])
                    
                    # Charger les métadonnées (dates de modification)
                    fichiers_metadata = {}
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            fichiers_metadata = json.load(f)
                    
                    # Identifier les changements
                    fichiers_actuels_set = set(fichiers_actuels.keys())
                    nouveaux_fichiers = fichiers_actuels_set - fichiers_indexes
                    fichiers_supprimes = fichiers_indexes - fichiers_actuels_set
                    fichiers_modifies = set()
                    
                    # Détecter les modifications (changement de date)
                    for fichier in fichiers_actuels_set & fichiers_indexes:
                        mtime_actuel = fichiers_actuels[fichier]
                        mtime_indexe = fichiers_metadata.get(fichier, 0)
                        if mtime_actuel > mtime_indexe:
                            fichiers_modifies.add(fichier)
                    
                    # Traiter les changements
                    changements_effectues = False
                    
                    if fichiers_supprimes:
                        print(f"{len(fichiers_supprimes)} fichier(s) supprimé(s): {', '.join(fichiers_supprimes)}")
                        _supprimer_fichiers_de_db(collection, fichiers_supprimes)
                        changements_effectues = True
                    
                    if fichiers_modifies:
                        print(f"{len(fichiers_modifies)} fichier(s) modifié(s): {', '.join(fichiers_modifies)}")
                        print("Réindexation des fichiers modifiés...")
                        _supprimer_fichiers_de_db(collection, fichiers_modifies)
                        _indexer_fichiers_incrementale(data_path, fichiers_modifies, collection)
                        changements_effectues = True
                    
                    if nouveaux_fichiers:
                        print(f"{len(nouveaux_fichiers)} nouveau(x) fichier(s) détecté(s): {', '.join(nouveaux_fichiers)}")
                        print("Indexation incrémentale en cours...")
                        _indexer_fichiers_incrementale(data_path, nouveaux_fichiers, collection)
                        changements_effectues = True
                    
                    if changements_effectues:
                        # Mettre à jour les métadonnées
                        _sauvegarder_metadata(metadata_path, fichiers_actuels)
                        return True
                    else:
                        print(f"Base de données à jour ({count} chunks, {len(fichiers_indexes)} fichiers)")
                        return False
                else:
                    print(f"Base de données déjà indexée ({count} chunks trouvés)")
                    return False
        except Exception as e:
            # Collection n'existe pas, on continue l'indexation
            print(f"Erreur lors de la vérification: {e}")
            pass
    
    print("Indexation complète en cours...")
    
    # Lire tous les fichiers
    documents: List[Dict[str, str]] = lire_fichiers_md(data_path)
    
    if not documents:
        print("Aucun fichier .md trouvé dans", data_path)
        return False
    
    # Découper en chunks
    tous_les_chunks: List[Dict[str, str]] = []
    for doc in documents:
        chunks = decouper_en_chunks(doc["contenu"])
        for chunk in chunks:
            tous_les_chunks.append({"texte": chunk, "fichier": doc["fichier"]})
    
    # Stocker dans ChromaDB
    stocker_dans_chromadb(tous_les_chunks, force_reindex=force_reindex)
    
    # Sauvegarder les métadonnées
    _sauvegarder_metadata(metadata_path, fichiers_actuels)
    
    print("✅ Indexation terminée avec succès !")
    return True


def _supprimer_fichiers_de_db(collection, fichiers: set) -> None:
    """
    Supprime tous les chunks associés aux fichiers spécifiés de la collection.
    
    Args:
        collection: Collection ChromaDB
        fichiers: Ensemble des noms de fichiers à supprimer
    """
    from src.ingestion.loader import supprimer_fichiers_de_chromadb
    supprimer_fichiers_de_chromadb(collection, fichiers)


def _sauvegarder_metadata(metadata_path: str, fichiers_metadata: Dict[str, float]) -> None:
    """
    Sauvegarde les métadonnées des fichiers (dates de modification).
    
    Args:
        metadata_path: Chemin vers le fichier de métadonnées JSON
        fichiers_metadata: Dictionnaire {nom_fichier: timestamp_modification}
    """
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(fichiers_metadata, f, indent=2)


def _indexer_fichiers_incrementale(data_path: str, fichiers: set, collection) -> bool:
    """
    Indexe uniquement les fichiers spécifiés de manière incrémentale.
    
    Args:
        data_path: Chemin du dossier contenant les fichiers
        fichiers: Ensemble des noms de fichiers à indexer
        collection: Collection ChromaDB existante
    
    Returns:
        True si l'indexation a réussi
    """
    from src.ingestion.loader import ajouter_a_chromadb
    
    # Lire uniquement les nouveaux fichiers
    documents: List[Dict[str, str]] = []
    for nom_fichier in fichiers:
        chemin_complet = os.path.join(data_path, nom_fichier)
        if os.path.exists(chemin_complet):
            with open(chemin_complet, "r", encoding="utf-8") as f:
                documents.append({"fichier": nom_fichier, "contenu": f.read()})
    
    print(f"📄 {len(documents)} nouveau(x) fichier(s) lu(s).")
    
    # Découper en chunks
    nouveaux_chunks: List[Dict[str, str]] = []
    for doc in documents:
        chunks = decouper_en_chunks(doc["contenu"])
        for chunk in chunks:
            nouveaux_chunks.append({"texte": chunk, "fichier": doc["fichier"]})
    
    # Ajouter à la collection existante
    ajouter_a_chromadb(collection, nouveaux_chunks)
    print("✅ Indexation incrémentale terminée avec succès !")
    return True


if __name__ == "__main__":
    # Script exécuté directement
    indexer_donnees(force_reindex=True)