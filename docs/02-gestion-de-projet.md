# 02 — Gestion de projet

## 2.1 Cadre

> **[À COMPLÉTER par le porteur du projet]**
> - Cadre exact : projet de formation **DWWM**, projet personnel, amorçage d'une
>   création d'entreprise ?
> - **Rôle(s)** tenu(s) : conception, développement full-stack, design, ops — préciser
>   ce qui a été fait seul et ce qui a été délégué / sous-traité.
> - **Équipe** : d'après l'historique Git, le développement est **quasi
>   exclusivement solo** (un contributeur principal, ~90 % des commits ; le reste =
>   commits de fusion et mises à jour automatiques de dépendances). Confirmer s'il y a
>   eu des contributions ponctuelles (design, relecture, tests utilisateurs).

## 2.2 Chronologie (d'après l'historique Git)

| Repère | Date |
|---|---|
| Premier commit | **18 novembre 2025** |
| Dernier commit à date de rédaction | **9 août 2026** |
| Durée | ~9 mois |
| Volume | **305 commits**, **26 *pull requests* fusionnées** (jusqu'à la #57 en comptant les branches Dependabot) |

> **[À COMPLÉTER]** Découpage en phases / sprints réels : dates de début et de fin,
> objectif de chaque itération. La mémoire projet évoque un « Sprint 1 — Wizard
> d'onboarding 4 étapes » ; préciser la cadence (hebdomadaire ? à la fonctionnalité ?)
> et l'outil de suivi (Trello / Notion / GitHub Projects / autre).

Grandes vagues de travail lisibles dans les noms de branches :
- **Fondations** : authentification, tableau de bord, ressources, équipe.
- **Modules métier** : planning (le plus gros — 16 migrations), qualité, messagerie,
  tâches, SMS.
- **Onboarding** : assistant en 5 étapes.
- **Monétisation** (été 2026) : app `billing`, intégration Stripe, offre gratuite du
  tableau de bord, gestion des impayés et du ré-abonnement — une dizaine de branches
  `feat/billing`, `feat/offre-gratuite-*`, `fix/reabonnement-*`, `fix/stripe-*`.
- **Sécurité** : plusieurs vagues d'audit (`fix/idor-critiques-audit-20260709`, tests
  `test_hardening_20260710`…).
- **Back-office admin** : durcissement complet (2FA, IP whitelist, audit log).

## 2.3 Méthode de travail

> **[À COMPLÉTER]** Rituels éventuels (revue hebdo, backlog priorisé), gestion des
> priorités, façon de décider quoi faire ensuite.

Ce qui est **observable dans le dépôt** :

### Workflow Git

- **Branche par sujet** puis ***pull request*** vers `main` (jamais de commit direct
  sur `main`). Nommage conventionnel : `feat/…`, `fix/…`, `chore/…`, `docs/…`,
  `refactor/…`.
- **Conventional Commits** (en français) sur la période récente : `fix(worker): …`,
  `chore(billing): …`. Les commits plus anciens sont en prose libre, parfois préfixés
  d'un code d'audit interne (`C78 — SÉCURITÉ ADMIN: …`).
- **Déploiement continu** : la fusion sur `main` déclenche le déploiement Scalingo
  (voir [chapitre 10](10-deploiement-exploitation.md)).
- Branche `dev` d'intégration en complément de `main`.

### Traçabilité des décisions techniques

Le projet **n'a pas de dossier d'ADR** (Architecture Decision Records) ni de wiki. Les
décisions et leur justification vivent :

1. **dans de longs commentaires de code**, souvent en tête de fichier
   (`Procfile`, `settings.py`, `permissions.py`, `auth.interceptor.ts`…), datés et
   argumentés ;
2. **sous forme de codes d'audit** (`C3`, `E1`, `M2`, `S21`, `Q05`…) qui relient un
   commentaire de code, un commit et un test de non-régression daté ;
3. **dans la mémoire projet** (notes markdown de suivi hors dépôt).

Cette documentation `docs/` est le premier effort de consolidation de ces éléments
épars en un ensemble navigable.

### Outils

| Domaine | Outil |
|---|---|
| Hébergement du code | GitHub (`Inostra38/lelienofficinal`, privé) |
| CI/CD | GitHub Actions |
| Sécurité continue | Dependabot, OWASP ZAP (hebdo) |
| Supervision | Sentry |
| Hébergement applicatif | Scalingo (France) |
| Paiement | Stripe |
| E-mail transactionnel | Mailgun (EU) |
| SMS | SMS Partner |
| Assistant IA | API Anthropic |
| Suivi de tâches | **[À COMPLÉTER]** |
| Maquettage | **[À COMPLÉTER]** (voir [chapitre 04](04-specifications-fonctionnelles.md)) |

## 2.4 Gestion de la qualité et de la dette

- **Batterie de tests priorisée** maintenue dans `fichiers MD/TESTS.md` (P1/P2/P3,
  marquage fait / à faire).
- **Dette technique assumée et documentée** — le [chapitre 12](12-limites-dette-roadmap.md)
  en tient le registre, avec pour chaque point le risque et la correction prévue.
- **Priorisation explicite** : au stade MVP, la règle est « faire tester l'application
  d'abord », le durcissement structurel et la validation terrain de la paie sont
  différés à la fin du MVP.
