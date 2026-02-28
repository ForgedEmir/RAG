"""
Module de génération : envoie la question + les passages trouvés
à l'IA DeepSeek pour obtenir une réponse naturelle.
"""
import os
import logging
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

# Créer un logger pour ce module
logger = logging.getLogger(__name__)

# Charger la clé API depuis le fichier .env
load_dotenv()

# --- Client OpenAI créé une seule fois (singleton) ---
# Évite de recréer la connexion à chaque question posée
_api_key = os.getenv("OPENAI_API_KEY")
_client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com"
) if _api_key else None


def generer_reponse(question: str, passages: List[str], sources: List[str] = None) -> str:
    """
    Génère une réponse en se basant UNIQUEMENT sur les passages fournis.

    Args:
        question : la question de l'utilisateur
        passages : liste de textes pertinents trouvés dans la base
        sources  : liste des noms de fichiers d'où proviennent les passages

    Returns:
        La réponse générée par l'IA DeepSeek
    """
    if not _client:
        raise ValueError("Clé OPENAI_API_KEY introuvable. Vérifiez votre fichier .env")

    # Fusionner tous les passages en un seul bloc de texte
    contexte = "\n\n".join(passages)

    # Préparer la liste des sources pour que l'IA puisse les citer
    liste_sources = ", ".join(sources) if sources else "sources inconnues"

    # Envoyer la question à l'IA avec les instructions et le contexte
    response = _client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant spécialisé dans le lore du jeu Aethelgard Online. "
                    "Réponds uniquement avec les informations du contexte ci-dessous. "
                    "N'invente rien. Si tu ne trouves pas l'info, dis-le simplement. "
                    "Cite le fichier source entre parenthèses quand tu donnes une information "
                    f"(sources disponibles : {liste_sources}).\n\n"
                    f"Contexte :\n{contexte}"
                )
            },
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=0.2
    )

    logger.info(f"Réponse générée pour la question : '{question}'")

    # Extraire et retourner le texte de la réponse
    return response.choices[0].message.content.strip()
