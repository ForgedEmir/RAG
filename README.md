# Projet Oracle — Assistant Intelligent pour le Lore

Le **Projet Oracle** est un assistant conversationnel intelligent (RAG) conçu pour interagir avec l'univers et le lore de votre jeu. Les joueurs peuvent poser des questions en langage naturel et obtenir des réponses fiables, basées *exclusivement* sur vos documents officiels.

---

## 🚀 Prérequis

Pour faire fonctionner le projet sur votre machine, vous aurez besoin de :
- **Python 3.11** (Recommandé pour la stabilité avec les modèles d'IA)
- **Git** (Pour cloner le dépôt)

---

## 🛠️ Installation

**1. Cloner le projet**
```bash
git clone https://votre-repo-gitlab.com/lorekeepers/projet-oracle.git
cd projet-oracle
```

**2. Créer un environnement virtuel**
Il est fortement recommandé de créer un environnement virtuel pour isoler les dépendances.
```bash
# Sous Windows
python -m venv venv
venv\Scripts\activate

# Sous MacOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Installer les dépendances**
Le fichier `requirements.txt` contient toutes les bibliothèques nécessaires (Flask, ChromaDB, OpenAI, etc.).
```bash
pip install -r requirements.txt
```

---

## 🔐 Configuration

L'assistant utilise l'intelligence artificielle de **DeepSeek** pour générer les réponses, et **FastEmbed** pour comprendre le texte localement (en français) sans surcharger votre machine.

Vous devez fournir votre propre clé API DeepSeek.

1. Faites une copie du fichier `.env.example` et renommez-la en `.env` :
   ```bash
   # Sous Windows
   copy .env.example .env

   # Sous MacOS / Linux
   cp .env.example .env
   ```
2. Ouvrez ce nouveau fichier `.env` et remplacez `"votre_cle_api_ici"` par votre véritable clé API **DeepSeek** (et non OpenAI). 
*(Note : Ce fichier est ignoré par Git et restera strictement confidentiel sur votre machine).*

---

## 🏃‍♂️ Lancement du projet

Le projet est conçu pour être lancé via un seul point d'entrée qui s'occupe de tout : l'ingestion de vos documents de lore et le lancement du serveur web.

1. Placez vos documents Markdown (`.md`) dans le dossier `data/sample/`.
2. Lancez l'application :
```bash
python main.py
```
3. L'intelligence artificielle va lire vos documents, les découper intelligemment et les stocker dans la base de données. 
4. Une fois l'indexation terminée, le serveur sera accessible à l'adresse : `http://127.0.0.1:5000`

---

## 👥 L'équipe Lorekeepers

- **Emir** : Ingestion des données
- **Ediz** : Recherche vectorielle (Base de données)
- **Nicolas** : Génération de réponses (IA)
- **Tom** : Interface Utilisateur & Documentation