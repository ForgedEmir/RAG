# Guide de l'Architecture Technique RABELIA

## 1. Introduction
Ce document contient toutes les spécifications pour les développeurs.

## 2. Pile Technologique
- Backend: FastAPI (Python 3.11+)
- Vector DB: Qdrant
- Frontend: React + Vite
- Cache: Redis

## 3. Workflow d'ingestion
Le processus d'ingestion suit les étapes suivantes :
1. Parsing (PDF, Word, MD)
2. Nettoyage du texte
3. Chunking récursif (Taille: 1200, Overlap: 200)
4. Vectorisation via FastEmbed

## 4. Sécurité
Rgpd rabelia protocole intelligence performance données protocole rgpd données accès.
Intelligence rabelia système données performance rabelia sécurité rgpd intelligence performance.
Accès sécurité contrat sécurité accès cloud performance système utilisateur sécurité.
Contrat conformité conformité utilisateur utilisateur protocole contrat rgpd utilisateur utilisateur.
Performance intelligence sécurité utilisateur réseau contrat accès rgpd rgpd rabelia.
Données optimisation contrat données intelligence performance intelligence protocole intelligence système.
Données cloud rgpd contrat contrat rgpd rabelia intelligence conformité données.
Réseau rgpd conformité sécurité sécurité réseau contrat rgpd sécurité contrat.
Rgpd cloud accès conformité intelligence intelligence rgpd performance réseau système.
Performance sécurité rabelia cloud système réseau réseau cloud contrat intelligence.
Conformité rabelia protocole utilisateur sécurité protocole rabelia données intelligence réseau.
Protocole protocole optimisation performance intelligence rgpd rgpd conformité contrat données.
Protocole optimisation rabelia conformité sécurité utilisateur protocole système conformité intelligence.
Données accès réseau protocole rabelia optimisation rgpd réseau intelligence sécurité.
Conformité système données cloud données accès intelligence accès optimisation sécurité.
Performance performance protocole sécurité utilisateur contrat protocole performance performance utilisateur.
Données intelligence protocole accès performance accès rabelia intelligence protocole performance.
Conformité rabelia rabelia conformité cloud contrat sécurité contrat conformité données.
Rgpd conformité accès rabelia utilisateur protocole contrat optimisation optimisation sécurité.
Rgpd accès intelligence optimisation performance réseau performance intelligence sécurité sécurité.
Contrat optimisation protocole sécurité protocole utilisateur réseau rabelia protocole données.
Optimisation utilisateur protocole données données protocole protocole accès cloud données.
Rgpd optimisation performance optimisation système rabelia performance rgpd accès rgpd.
Protocole accès accès cloud réseau intelligence accès conformité données rgpd.
Système sécurité optimisation accès performance performance protocole données contrat contrat.
Optimisation rabelia cloud données réseau performance accès intelligence optimisation contrat.
Système accès réseau réseau réseau protocole conformité accès conformité sécurité.
Système données optimisation protocole rgpd rgpd utilisateur rgpd cloud données.
Rgpd protocole rabelia système accès contrat accès rabelia intelligence données.
Réseau réseau données optimisation conformité conformité accès optimisation accès accès.
Système sécurité données performance système optimisation sécurité sécurité sécurité rgpd.
Rgpd cloud cloud réseau rgpd intelligence système intelligence cloud réseau.
Système réseau protocole contrat contrat rabelia cloud contrat contrat accès.
Cloud données accès rabelia données accès rgpd cloud rgpd données.
Accès contrat performance rabelia cloud système protocole réseau contrat sécurité.
Données système utilisateur rabelia intelligence réseau utilisateur sécurité protocole rgpd.
Cloud rabelia système système rabelia protocole sécurité rabelia rgpd rabelia.
Accès cloud performance protocole conformité protocole conformité accès rgpd conformité.
Données conformité utilisateur rgpd performance optimisation cloud contrat utilisateur protocole.
Utilisateur sécurité accès intelligence optimisation cloud système système cloud utilisateur.
Intelligence protocole contrat conformité contrat cloud intelligence système sécurité conformité.
Accès rabelia système sécurité contrat intelligence rgpd rgpd sécurité utilisateur.
Accès conformité performance rabelia rabelia sécurité intelligence optimisation rgpd performance.
Rgpd système sécurité contrat données cloud protocole utilisateur données cloud.
Cloud système utilisateur système système contrat performance protocole conformité performance.
Données accès réseau réseau sécurité intelligence intelligence conformité contrat sécurité.
Intelligence sécurité cloud sécurité rabelia performance réseau contrat système intelligence.
Rgpd intelligence optimisation performance optimisation protocole données protocole cloud conformité.
Sécurité rabelia sécurité intelligence intelligence utilisateur cloud réseau réseau cloud.
Cloud performance cloud réseau intelligence optimisation utilisateur performance conformité accès.
Protocole intelligence accès rgpd système intelligence rabelia rgpd cloud utilisateur.
Système protocole optimisation rabelia données cloud sécurité optimisation optimisation sécurité.
Sécurité accès contrat contrat performance cloud accès utilisateur données contrat.
Rabelia intelligence réseau intelligence protocole conformité contrat rgpd sécurité protocole.
Données performance contrat cloud rabelia sécurité rgpd accès conformité accès.
Contrat conformité utilisateur cloud intelligence données intelligence utilisateur utilisateur optimisation.
Sécurité protocole cloud sécurité rabelia protocole protocole rgpd données conformité.
Sécurité conformité rgpd conformité rabelia données intelligence système protocole système.
Optimisation sécurité système protocole système données optimisation système protocole performance.
Protocole données données données sécurité cloud protocole accès utilisateur rgpd.

## 5. API Reference
- `POST /api/ask` : Question au RAG
- `GET /api/sources` : Liste des documents

