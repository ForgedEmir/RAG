"""
Module contenant des fonctions utilitaires pour l'application.
"""


def valider_question(question) -> bool:
    """
    Valide qu'une question est valide (non vide et assez longue).
    
    Args:
        question: La question à valider
        
    Returns:
        True si la question est valide, False sinon
    """
    if not isinstance(question, str):
        return False
    
    question_nettoyee = question.strip()
    return len(question_nettoyee) >= 2


def nettoyer_texte(texte) -> str:
    """
    Nettoie un texte en supprimant les espaces superflus.
    
    Args:
        texte: Le texte à nettoyer
        
    Returns:
        Le texte nettoyé
    """
    if texte is None:
        return ""
    
    if not isinstance(texte, str):
        return ""
    
    # Remplace les tabulations et sauts de ligne par des espaces
    texte = texte.replace('\t', ' ').replace('\n', ' ')
    
    # Supprime les espaces multiples
    while '  ' in texte:
        texte = texte.replace('  ', ' ')
    
    return texte.strip()


def formater_nom_fichier(nom_fichier: str) -> str:
    """
    Formate un nom de fichier en enlevant l'extension .md.
    
    Args:
        nom_fichier: Le nom du fichier
        
    Returns:
        Le nom du fichier sans l'extension .md
    """
    if not nom_fichier:
        return ""
    
    if nom_fichier.endswith('.md'):
        return nom_fichier[:-3]
    
    return nom_fichier


def extraire_extension(nom_fichier: str):
    """
    Extrait l'extension d'un fichier.
    
    Args:
        nom_fichier: Le nom du fichier
        
    Returns:
        L'extension sans le point, ou None si pas d'extension
    """
    if not nom_fichier:
        return None
    
    if '.' not in nom_fichier:
        return None
    
    # Prend la dernière partie après le dernier point
    parties = nom_fichier.split('.')
    
    # Si le fichier commence par un point (.gitignore), retourne ce qui suit
    if len(parties) == 2 and parties[0] == '':
        return parties[1]
    
    return parties[-1]


def compter_mots(texte) -> int:
    """
    Compte le nombre de mots dans un texte.
    
    Args:
        texte: Le texte à analyser
        
    Returns:
        Le nombre de mots
    """
    if texte is None:
        return 0
    
    if not isinstance(texte, str):
        return 0
    
    if not texte.strip():
        return 0
    
    # split() sans argument gère automatiquement les espaces multiples et les sauts de ligne
    mots = texte.split()
    return len(mots)


def tronquer_texte(texte, longueur_max: int = 100, suffixe: str = "...") -> str:
    """
    Tronque un texte à une longueur maximale.
    
    Args:
        texte: Le texte à tronquer
        longueur_max: La longueur maximale (défaut: 100)
        suffixe: Le suffixe à ajouter si le texte est tronqué (défaut: "...")
        
    Returns:
        Le texte tronqué avec le suffixe si nécessaire
    """
    if texte is None:
        return ""
    
    if not isinstance(texte, str):
        return ""
    
    if len(texte) <= longueur_max:
        return texte
    
    return texte[:longueur_max] + suffixe
