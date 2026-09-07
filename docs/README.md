# Documentation technique — Le Lien Officinal

> SaaS B2B à destination des pharmacies d'officine.
> Frontend **Angular 20** · Backend **Django 6 / DRF** · Temps réel **Django Channels** ·
> Déploiement **Scalingo**.

Cette documentation décrit l'architecture, les choix techniques et les mécanismes de
sécurité de la plateforme. Elle sert de support à la soutenance du titre professionnel
**DWWM — Développeur Web et Web Mobile** (RNCP niveau 5) et de référence d'ingénierie
pour le projet.

## Comment lire cette documentation

| Vous êtes… | Commencez par |
|---|---|
| Membre du jury / évaluateur | [01 — Présentation](01-presentation-projet.md) puis [03 — Architecture générale](03-architecture-generale.md), et l'[annexe compétences DWWM](annexe-competences-dwwm.md) |
| Développeur qui reprend le projet | [03 — Architecture générale](03-architecture-generale.md) → [05](05-frontend-angular.md) / [06](06-backend-django.md) → [10 — Déploiement](10-deploiement-exploitation.md) |
| Responsable sécurité / conformité | [08 — Sécurité & conformité](08-securite-conformite.md) |

## Sommaire

| # | Chapitre | Contenu |
|---|---|---|
| 01 | [Présentation du projet](01-presentation-projet.md) | Genèse, besoin métier, cible, proposition de valeur, offre freemium, périmètre fonctionnel |
| 02 | [Gestion de projet](02-gestion-de-projet.md) | Méthodologie, organisation, outils, conventions Git, historique des décisions |
| 03 | [Architecture générale](03-architecture-generale.md) | Vue d'ensemble, monorepo, stack justifiée, flux principaux, diagramme système |
| 04 | [Spécifications fonctionnelles](04-specifications-fonctionnelles.md) | User stories, parcours, arborescence de navigation, charte graphique |
| 05 | [Front-end Angular](05-frontend-angular.md) | Structure standalone, routing & guards, intercepteurs, état, UI, temps réel, build |
| 06 | [Back-end Django](06-backend-django.md) | Apps, configuration, API REST, permissions, throttling, tâches asynchrones |
| 07 | [Modèle de données](07-modele-de-donnees.md) | Diagrammes entité-association, multi-tenant, overlay de préférences, migrations |
| 08 | [Sécurité & conformité](08-securite-conformite.md) | RGPD / données de santé, chiffrement, double authentification JWT, audits menés |
| 09 | [Modules transverses](09-modules-transverses.md) | Facturation Stripe, SMS, assistant IA |
| 10 | [Déploiement & exploitation](10-deploiement-exploitation.md) | Scalingo, CI/CD GitHub Actions, environnements, supervision |
| 11 | [Tests & qualité](11-tests-qualite.md) | Stratégie de tests, couverture, analyse statique, sécurité automatisée |
| 12 | [Limites, dette technique & perspectives](12-limites-dette-roadmap.md) | État MVP, dette assumée, roadmap |
| A1 | [Annexe — Compétences DWWM](annexe-competences-dwwm.md) | Table de correspondance CP1 → CP8 |
| A2 | [Annexe — Glossaire](annexe-glossaire.md) | Vocabulaire métier de l'officine |

## Version web (synthèse navigable)

Une synthèse de cette documentation, avec sommaire latéral et diagrammes rendus, est
publiée comme page web privée :
**<https://claude.ai/code/artifact/1fb576b1-47bb-4cf1-aaf9-e43d4b96db45>**

Les fichiers Markdown de ce dossier restent la source de vérité (plus détaillée).

## Schémas

Les diagrammes (architecture système, modèle de données, séquences d'authentification)
sont écrits en [Mermaid](https://mermaid.js.org/) et rendus automatiquement par GitHub.
Leurs sources sont dans [`diagrams/`](diagrams/).

## Conventions

- Les extraits de code sont référencés `chemin/fichier.py:ligne` à partir de la racine
  du dépôt.
- Les commentaires du code source portent des identifiants d'audit (`C3`, `E1`, `S21`,
  `Q05`…) : ils tracent les corrections issues des revues de sécurité successives
  (voir [chapitre 08](08-securite-conformite.md)).
- « Officine » = pharmacie de ville. « Titulaire » = pharmacien propriétaire. Voir le
  [glossaire](annexe-glossaire.md).

---

*Version de la documentation : 1.0 — septembre 2026.*
