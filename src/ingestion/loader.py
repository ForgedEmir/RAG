from typing import Any, Dict, List
import chromadb
import os
import hashlib


def stocker_dans_chromadb(chunks_avec_meta: List[Dict[str, Any]], force_reindex: bool = False) -> Any:
    """
    Stocke les chunks dans ChromaDB.
    
    Args:
        chunks_avec_meta: Liste des chunks avec leurs métadonnées
        force_reindex: Si True, supprime et recrée la collection
    
    Returns:
        La collection ChromaDB
    """
    # Chemin absolu de la base de données
    base_dir = os.path.dirname(__file__)
    db_path = os.path.join(base_dir, "chroma_db")
    
    client = chromadb.PersistentClient(path=db_path)
    
    # Supprimer la collection existante si force_reindex est True
    if force_reindex:
        try:
            client.delete_collection("lore")
            print("🗑️  Collection existante supprimée")
        except:
            pass
    
    # Créer ou récupérer la collection
    try:
        collection = client.create_collection("lore")
    except:
        # La collection existe déjà
        collection = client.get_collection("lore")

    for i, chunk in enumerate(chunks_avec_meta):
        # Générer un ID unique basé sur le contenu
        chunk_id = _generer_id_unique(chunk["texte"], chunk["fichier"], i)
        collection.add(
            ids=[chunk_id],
            documents=[chunk["texte"]],
            metadatas=[{"fichier": chunk["fichier"]}]
        )

    print(f"💾 {len(chunks_avec_meta)} chunks stockés dans ChromaDB.")
    return collection


def ajouter_a_chromadb(collection: Any, chunks_avec_meta: List[Dict[str, Any]]) -> None:
    """
    Ajoute de nouveaux chunks à une collection ChromaDB existante.
    
    Args:
        collection: Collection ChromaDB existante
        chunks_avec_meta: Liste des nouveaux chunks avec leurs métadonnées
    """
    # Obtenir le nombre actuel de chunks pour générer des IDs uniques
    count_actuel = collection.count()
    
    for i, chunk in enumerate(chunks_avec_meta):
        # Générer un ID unique basé sur le contenu
        chunk_id = _generer_id_unique(chunk["texte"], chunk["fichier"], count_actuel + i)
        
        try:
            collection.add(
                ids=[chunk_id],
                documents=[chunk["texte"]],
                metadatas=[{"fichier": chunk["fichier"]}]
            )
        except Exception as e:
            # Si l'ID existe déjà, on continue
            print(f"⚠️  Chunk déjà existant, ignoré: {e}")
            continue
    
    print(f"💾 {len(chunks_avec_meta)} nouveaux chunks ajoutés à ChromaDB.")


def supprimer_fichiers_de_chromadb(collection: Any, fichiers: set) -> None:
    """
    Supprime tous les chunks associés aux fichiers spécifiés.
    
    Args:
        collection: Collection ChromaDB
        fichiers: Ensemble des noms de fichiers à supprimer
    """
    # Récupérer tous les documents
    all_data = collection.get()
    
    if not all_data or 'ids' not in all_data or 'metadatas' not in all_data:
        return
    
    # Identifier les IDs à supprimer
    ids_a_supprimer = []
    for i, metadata in enumerate(all_data['metadatas']):
        if metadata and metadata.get('fichier') in fichiers:
            ids_a_supprimer.append(all_data['ids'][i])
    
    # Supprimer les chunks
    if ids_a_supprimer:
        collection.delete(ids=ids_a_supprimer)
        print(f"🗑️  {len(ids_a_supprimer)} chunks supprimés de ChromaDB.")


def _generer_id_unique(texte: str, fichier: str, index: int) -> str:
    """
    Génère un ID unique pour un chunk basé sur son contenu.
    
    Args:
        texte: Contenu du chunk
        fichier: Nom du fichier source
        index: Index du chunk
    
    Returns:
        Un ID unique sous forme de hash
    """
    # Créer un hash du contenu pour garantir l'unicité
    contenu = f"{fichier}_{index}_{texte[:50]}"
    hash_obj = hashlib.md5(contenu.encode('utf-8'))
    return f"chunk_{hash_obj.hexdigest()[:16]}"