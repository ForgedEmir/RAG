# Procédure d'Onboarding Client — RABELIA

## Vue d'ensemble

L'onboarding d'un nouveau client B2B se déroule en 4 phases sur une période de 2 à 4 semaines selon la complexité du déploiement.

## Phase 1 : Kickoff (Semaine 1)

**Responsable :** Customer Success Manager (CSM)

Actions :
1. Réunion de lancement avec les parties prenantes du client (30-60 min)
2. Recueil des besoins spécifiques et des cas d'usage prioritaires
3. Identification des sources documentaires à indexer
4. Configuration des accès administrateurs

Livrables :
- Fiche projet signée
- Accès à l'environnement sandbox

## Phase 2 : Intégration documentaire (Semaines 1-2)

**Responsable :** Équipe technique Nexus

Actions :
1. Audit des documents à indexer (format, volume, sensibilité)
2. Préparation du pipeline d'ingestion
3. Première indexation et validation de la qualité
4. Test de pertinence avec 20 questions représentatives

Formats acceptés :
- PDF, DOCX, PPTX, XLSX
- Markdown, TXT
- HTML, CSV
- Connecteurs natifs : SharePoint, Google Drive, Confluence

Livrables :
- Rapport de qualité RAG (précision, rappel, latence)
- Documentation du pipeline configuré

## Phase 3 : Formation (Semaine 3)

**Responsable :** CSM + équipe formation

Sessions de formation :
- **Utilisateurs finaux** (1h) : utilisation du chatbot, interprétation des sources
- **Administrateurs** (2h) : gestion des collections, réindexation, monitoring
- **Développeurs** (2h) : API REST, webhooks, intégration SSO

Ressources fournies :
- Guide utilisateur en PDF
- Accès à la base de connaissances Nexus
- Vidéos tutoriels

## Phase 4 : Mise en production (Semaine 4)

Actions :
1. Revue de sécurité (configuration RBAC, audit des accès)
2. Configuration des alertes monitoring
3. Bascule de l'environnement sandbox vers production
4. Point de contrôle J+7 avec le CSM

Critères de succès :
- Disponibilité > 99,5 %
- Satisfaction utilisateurs > 4/5 sur les premières semaines
- Taux de réponses pertinentes > 85 %

## Support post-onboarding

- Réunion mensuelle de suivi avec le CSM pendant les 3 premiers mois
- Accès au support technique via le portail client ou support@rabelia.io
- Hotline critique disponible 24/7 pour les incidents P1
