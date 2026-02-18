import os
import chromadb


def rechercher_passages(question: str) -> tuple[list[str], str]:
    """
    Fonction qui cherche les passages pertinents dans la base de données
    """
    # Connexion à ChromaDB (chemin base sur l'emplacement du fichier)
    base_dir = os.path.dirname(__file__)
    db_path = os.path.normpath(os.path.join(base_dir, "..", "ingestion", "chroma_db"))
    print(f"[DEBUG] Chemin de la base de données: {db_path}")
    
    client_db = chromadb.PersistentClient(path=db_path)

    # Récupérer la collection
    collection = client_db.get_or_create_collection(name="lore")
    
    # Vérifier le nombre de documents dans la collection
    count = collection.count()
    print(f"[DEBUG] Nombre de documents dans la collection 'lore': {count}")

    # Envoyer la question
    results = collection.query(
        query_texts=[question],
        n_results=3 # les 3 meilleurs résultats
    )

    documents = results.get("documents", [[]])
    passages = documents[0] if documents else []
    print(f"[DEBUG] Question: {question}")
    print(f"[DEBUG] Nombre de passages trouvés: {len(passages)}")
    if passages:
        print(f"[DEBUG] Premier passage: {passages[0][:100]}...")
    
    return passages, question