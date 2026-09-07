# 01 — Présentation du projet

## 1.1 En une phrase

**Le Lien Officinal** est une application web (SaaS B2B) qui réunit dans un seul espace
les outils du quotidien d'une **pharmacie d'officine** : un tableau de bord de
raccourcis vers les ressources métier, un planning d'équipe assisté par IA, un module
d'assurance qualité, une messagerie interne chiffrée, la gestion des tâches et l'envoi
de SMS aux patients.

## 1.2 Genèse

> **[À COMPLÉTER par le porteur du projet]**
>
> Éléments à fournir pour cette section :
> - Le **constat de départ** : quel problème concret vit une équipe officinale
>   aujourd'hui (outils éparpillés, planning fait à la main sur tableur, procédures
>   qualité dans un classeur, etc.) ?
> - **D'où vient l'idée** (expérience personnelle, entourage pharmacien, étude de
>   marché) ?
> - **Depuis quand** le projet est en développement, et dans quel cadre (formation au
>   titre Développeur Web, projet personnel, création d'entreprise).
>
> *Trame proposée, à valider :* « Une officine utilise en moyenne 5 à 10 outils
> distincts sans lien entre eux. Le planning, en particulier, est un casse-tête
> récurrent : gardes, temps partiels, apprentis en CFA, repos légal… Le Lien
> Officinal est né de ce constat : rassembler ces outils et automatiser la partie la
> plus pénible — la composition du planning. »

## 1.3 Cible

| | |
|---|---|
| **Marché** | ~20 000 officines en France (pharmacies de ville) |
| **Client** | le **titulaire** (pharmacien propriétaire), décideur de l'abonnement |
| **Utilisateurs** | toute l'équipe : titulaire, adjoints, préparateurs, étudiants, apprentis — chacun avec ses permissions et son code PIN |
| **Contexte d'usage** | au comptoir et en arrière-boutique, sur poste fixe surtout, tablette à l'occasion — d'où le soin porté au responsive et à l'impression |

## 1.4 Proposition de valeur

D'après le positionnement commercial (site vitrine) :

- **« Toute l'officine au même endroit »** — un espace unique plutôt qu'une
  collection d'outils sans lien.
- **Le planning assisté par IA comme produit d'appel** : on décrit l'officine une fois
  (horaires, contrats, gardes, indisponibilités), l'assistant génère un planning
  équilibré en quelques secondes, l'utilisateur ajuste au glisser-déposer et publie.
  Le récapitulatif de paie (heures sup, absences, majorations de nuit) se met à jour
  en direct.
- **Pensé « comptoir », pas « service informatique »** — prise en main immédiate.
- **Conçu pour la santé** — hébergement en France, chiffrement des échanges, accès par
  rôle, conformité RGPD par conception.

## 1.5 Modèle économique — freemium

Décision du 2026-07-19, inscrite dans le code (`apps/billing/permissions.py`) :

| Périmètre | Accès | Détail |
|---|---|---|
| **Tableau de bord de raccourcis** + catégories + cartes + favoris + notes + profil officine + **gestion d'équipe** | **Gratuit, définitivement, sans carte bancaire** | Aucune de ces vues ne porte de contrôle d'abonnement ; un test automatisé (`test_free_tier.py`) verrouille cette garantie |
| **Suite complète** : planning IA, qualité, messagerie, tâches, SMS | **Essai 30 jours** puis abonnement | `small` (< 10 collaborateurs) : **39 € HT/mois** · `large` (≥ 10) : **59 € HT/mois** *(tarifs vitrine — à confirmer avec les prix Stripe réels)* |

Un accès expiré ne bloque jamais l'application : les modules payants renvoient un
code **HTTP 402** et l'utilisateur retombe sur le tableau de bord gratuit. Voir
[chapitre 09](09-modules-transverses.md).

**Crédits SMS** : hors abonnement, achetés par packs (100 / 250 / 500 SMS), facturés
séparément.

## 1.6 Périmètre fonctionnel

| Module | Contenu | Gratuit / Payant |
|---|---|---|
| **Tableau de bord** | Raccourcis vers les ressources métier (Ameli, ANSM, grossistes, laboratoires…) : catégories, 3 vues (compacte / icônes / liste), favoris, notes courtes et longues, glisser-déposer, recherche. Cartes officielles (validées), partenaires (laboratoires) ou privées. Recommandation communautaire de liens. | Gratuit |
| **Équipe** | Collaborateurs (sans compte, connexion par PIN), rôles, 8 permissions fonctionnelles, historique de contrats, verrouillage anti-force-brute, journal de connexion. | Gratuit |
| **Planning** | Vue semaine / mois, shifts publiés ou brouillon, gardes jour/nuit, absences, ajustements horaires, modèles de semaine, **génération IA**, moteur de paie analytique. | Payant |
| **Qualité** | Procédures hiérarchisées et versionnées, catégories, pilotes, journal de lecture, non-conformités (mineure/majeure/critique), actions correctives, **assistant IA de rédaction**. | Payant |
| **Messagerie** | Conversations d'équipe **chiffrées au repos**, temps réel (WebSocket), accusés de lecture. Adaptée aux échanges touchant aux données de santé. | Payant |
| **Tâches** | Tâches personnelles ou assignées, priorités, commentaires, kanban. | Payant |
| **SMS patients** | Modèles avec variables, comptage GSM-7 / Unicode, crédits, envoi asynchrone, accusés de réception temps réel. | Payant (crédits) |
| **Back-office admin** | Gestion du catalogue de ressources, validation des recommandations communautaires, suivi des abonnements. Sécurité renforcée (2FA, IP whitelist). | Interne |

## 1.7 Parcours d'entrée — onboarding

Assistant en **5 étapes** (`features/onboarding/steps/`) : profil de l'officine →
centres d'intérêt (catégories) → premières ressources → équipe → récapitulatif, puis
redirection vers le tableau de bord.
