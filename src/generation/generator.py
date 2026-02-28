"""
Ce module donne une "voix" à notre système.
Il envoie les textes qu'on a trouvés + la question à DeepSeek (notre IA), 
et lui demande de rédiger une réponse de façon naturelle au lieu de simplement copier-coller.
"""
import os
import logging
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

# On s'assure que les variables d'environnement (.env) sont bien lues
load_dotenv()

# On initialise le client OpenAI (ici configuré pour l'API de DeepSeek).
# On le fait une seule fois au chargement du fichier (singleton) plutôt que 
# de se reconnecter à chaque fois qu'un utilisateur pose une question.
_api_key = os.getenv("OPENAI_API_KEY")
_client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com"
) if _api_key else None


def generer_reponse(question: str, passages: List[str], sources: List[str] = None) -> str:
    """
    Le prompt "RAG" classique.
    On donne des instructions strictes à l'IA pour qu'elle ne se base QUE
    sur les morceaux de texte qu'on lui fournit, afin d'éviter les "hallucinations".
    """
    if not _client:
        raise ValueError("Clé OPENAI_API_KEY manquante. Vérifie ton fichier .env pour pouvoir utiliser l'IA.")

    # On colle tous les résultats trouvés par ChromaDB en un seul gros bloc de texte
    contexte = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"

    # L'appel à l'API LLM pour la complétion de chat
    response = _client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant spécialisé dans le lore du jeu Aethelgard Online. "
                    "Réponds uniquement en te basant sur les informations du contexte fourni. "
                    "N'invente absolument rien. Si l'information ne s'y trouve pas, dis-le honnêtement. "
                    "Assure-toi de citer le fichier source entre parenthèses lorsque tu donnes une information "
                    f"(pour t'aider, les sources de ce contexte sont : {liste_sources}).\n\n"
                    f"Voici ton contexte de référence :\n{contexte}"
                )
            },
            {
                "role": "user",
                "content": question
            }
        ],
        # Une température basse (0.2) rend l'IA plus factuelle et moins "créative/inventive"
        temperature=0.2
    )

    logger.info(f"L'IA a terminé de rédiger sa réponse.")
    
    # On renvoie juste le texte généré final
    return response.choices[0].message.content.strip()
