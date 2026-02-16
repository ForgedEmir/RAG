from src.generation.generateur import generer_reponse

question = "Qui est le roi ?"
passages = ["Le roi Aldric règne depuis 40 ans sur les Terres du Nord."]

reponse = generer_reponse(question, passages)

print(reponse)
