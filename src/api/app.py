from flask import Flask, request, jsonify
from src.search.recherche import rechercher_passages
from src.generation.generateur import generate_response

app = Flask(name)

@app.route("/ask", methods=["POST"])
def ask() -> jsonify():
    question = request.json["question"]
    passages = rechercher_passages(question)
    reponse = generate_response(question, passages)
    return jsonify({"reponse": reponse})

app.run()