# src/generation/generateur.py

import os
from dotenv import load_dotenv
from openai import OpenAI


def generer_reponse(question: str, passages: list[str]) -> str:
    """
    Génère une réponse basée UNIQUEMENT sur les passages fournis.

    Args:
        question (str): la question de l'utilisateur
        passages (list[str]): liste de passages de lore pertinents

    Returns:
        str: réponse générée par DeepSeek
    """

    # --------------------------------------------------
    # 1) Charger les variables d'environnement (.env)
    # --------------------------------------------------
    load_dotenv()
    # --------------------------------------------------
    # 2) Créer le client OpenAI (compatible DeepSeek)
    # --------------------------------------------------
    client = OpenAI(
        api_key= "sk-6dc5c23356a24645bb860d2811d8b768",
        base_url="https://api.deepseek.com"
    )

    # --------------------------------------------------
    # 3) Assembler les passages en un seul contexte
    # --------------------------------------------------
    contexte = "\n\n".join(passages)

    # --------------------------------------------------
    # 4) Construire le prompt
    # --------------------------------------------------

    # Message système = comportement du modèle
    system_prompt = (
        "Tu es un assistant spécialisé dans le lore. "
        "Réponds uniquement en utilisant les informations du contexte fourni. "
        "N'invente rien. Si l'information n'existe pas dans le contexte, "
        "dis clairement que ce n'est pas indiqué."
        "tu dois décrire aux mieux ce qui est en rappor avec la question a l'aide de ce qui ce trouve dans passage"
    )

    # Message utilisateur = données + question
    user_prompt = f"""
Contexte :
{contexte}

Question :
{question}
"""

    # --------------------------------------------------
    # 5) Appel au modèle DeepSeek
    # --------------------------------------------------
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2  # faible créativité = moins d'invention
    )

    # --------------------------------------------------
    # 6) Retourner la réponse texte
    # --------------------------------------------------
    return response.choices[0].message.content.strip()
