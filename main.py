from src.generation.generateur import generer_reponse
from src.search.recherche import rechercher_passages

question = "Qui est le souverain incontesté du Royaume Humain d'Aethelgard depuis le lancement du jeu il y a 10 ans. ?"

passages, _question_retournee = rechercher_passages(question)

if not passages:
    print("Aucun passage pertinent trouve.")
else:
    reponse = generer_reponse(question, passages)
    print(reponse)
