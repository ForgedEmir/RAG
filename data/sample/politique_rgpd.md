# Politique de Protection des Données Personnelles (RGPD)

## 1. Responsable du traitement

**RABELIA SAS**
Représentant légal : Directeur Général
DPO : dpo@rabelia.io

## 2. Données collectées

| Catégorie | Exemples | Base légale |
|---|---|---|
| Données d'identification | Nom, email, identifiant | Exécution du contrat |
| Données d'usage | Logs de requêtes, sessions | Intérêt légitime |
| Données techniques | Adresse IP, user-agent | Intérêt légitime |

Nous ne collectons **aucune donnée sensible** au sens de l'article 9 du RGPD (santé, opinions politiques, etc.).

## 3. Durée de conservation

- Données de compte actif : durée du contrat + 3 ans
- Logs d'audit : 12 mois glissants
- Données de facturation : 10 ans (obligation légale)
- Données anonymisées à des fins statistiques : illimitée

## 4. Droits des personnes

Conformément au RGPD, chaque utilisateur dispose des droits suivants :
- **Droit d'accès** : obtenir une copie de ses données
- **Droit de rectification** : corriger des données inexactes
- **Droit à l'effacement** : demander la suppression (sauf obligation légale)
- **Droit à la portabilité** : recevoir ses données en format structuré (JSON/CSV)
- **Droit d'opposition** : s'opposer au traitement pour des raisons légitimes

Pour exercer ces droits : privacy@rabelia.io

## 5. Transferts hors UE

Les données sont hébergées dans des datacenters situés en Union Européenne (France et Allemagne). Aucun transfert vers des pays tiers n'est effectué sans garanties appropriées (clauses contractuelles types de la Commission européenne).

## 6. Sécurité

- Chiffrement des données au repos (AES-256)
- Chiffrement des données en transit (TLS 1.3)
- Contrôle d'accès basé sur les rôles (RBAC)
- Masquage automatique des informations personnelles (PII) avant traitement LLM
- Audit de sécurité annuel par un tiers indépendant

## 7. Sous-traitants

| Sous-traitant | Service | Localisation |
|---|---|---|
| Qdrant | Base vectorielle | EU (Allemagne) |
| Redis | Cache | EU (France) |
| Supabase | Authentification | EU |
| Langfuse | Observabilité LLM | EU |
