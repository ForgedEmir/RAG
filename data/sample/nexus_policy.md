## Politique de Gouvernance des Données - Nexus AI

### 1. Introduction
La présente politique définit les standards de gestion des données au sein de la plateforme RABELIA. Elle s'applique à tous les traitements d'informations indexées dans le moteur RAG.

### 2. Confidentialité et Sécurité
Nexus utilise un pipeline de traitement sécurisé qui inclut :
- Le masquage systématique des informations identifiables (PII) avant l'envoi aux modèles de langage tiers.
- Le chiffrement des données au repos dans la base vectorielle Qdrant.
- Le contrôle d'accès basé sur les rôles (RBAC) pour chaque collection de documents.

### 3. Cycle de Vie des Données
- **Ingestion** : Les documents sont prétraités pour extraire le texte et les métadonnées.
- **Indexation** : Création de vecteurs d'embeddings de 384 dimensions.
- **Rétention** : Les données sont conservées tant que la collection est active, avec possibilité de purge programmée.

### 4. Conformité
Nexus est conçu pour aider les organisations à maintenir leur conformité RGPD en offrant une transparence totale sur les sources utilisées pour chaque réponse générée.
