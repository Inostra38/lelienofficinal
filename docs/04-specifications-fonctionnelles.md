# 04 — Spécifications fonctionnelles

> **Référentiel — bloc 2, `C4.a` :** conceptualiser l'application et **formaliser son
> schéma fonctionnel**. `Cr 4.a.3` — toutes les fonctionnalités listées et détaillées
> (§4.2) · `Cr 4.a.4` — **l'enchaînement des vues en fonction des actions et
> interactions** (§4.3). Sert aussi de référence au bloc 1 (`Cr 1.a.1`, conformité à la
> maquette). Détail en [annexe](annexe-referentiel-competences.md).

## 4.1 Acteurs

| Acteur | Description | Authentification |
|---|---|---|
| **Visiteur** | Prospect sur le site vitrine | — |
| **Titulaire** | Pharmacien propriétaire, administrateur de l'espace officine | e-mail + mot de passe (JWT) |
| **Collaborateur** | Membre de l'équipe (adjoint, préparateur, étudiant, apprenti) | session ouverte par le titulaire, puis **code PIN** pour signer les actions ; 8 permissions fonctionnelles |
| **Administrateur SaaS** | Exploitant de la plateforme (catalogue, recommandations, abonnements) | e-mail + mot de passe + **2FA TOTP** + IP autorisée |

## 4.2 User stories principales

### Onboarding & compte
- *En tant que* visiteur, *je veux* créer mon espace sans carte bancaire *afin de*
  tester la plateforme immédiatement.
- *En tant que* titulaire, *je veux* décrire mon officine, choisir mes centres
  d'intérêt et ajouter mon équipe en 5 étapes guidées *afin d'*être opérationnel
  rapidement.
- *En tant que* titulaire, *je veux* pouvoir demander la suppression de mon compte
  *afin de* faire valoir mon droit à l'effacement (RGPD) ; l'effacement est différé
  et annulable.

### Tableau de bord (gratuit)
- *En tant que* membre de l'équipe, *je veux* accéder d'un clic aux sites que
  j'utilise tous les jours (Ameli, ANSM, grossiste, laboratoires) *afin de* ne plus
  chercher dans mes favoris navigateur.
- *je veux* organiser ces raccourcis en catégories, en favoris, avec des notes
  courtes et longues *afin d'*adapter l'espace à mon officine.
- *je veux* choisir entre 3 vues (compacte, icônes, liste) *afin de* m'adapter à
  l'écran et à mes préférences.
- *je veux* proposer un lien utile à la communauté *afin qu'*il profite aux autres
  officines après validation.

### Équipe (gratuit)
- *En tant que* titulaire, *je veux* créer mes collaborateurs avec un rôle et des
  permissions fines *afin de* contrôler qui peut gérer le planning, la qualité, les
  tâches.
- *je veux* que le PIN se verrouille après 5 échecs *afin de* prévenir les essais
  malveillants.
- *je veux* consigner l'historique des contrats *afin de* garder une trace RH fiable.

### Planning (payant)
- *En tant que* manager, *je veux* décrire une fois mes horaires, contrats, gardes et
  indisponibilités, puis **laisser l'IA générer** un planning équilibré *afin de*
  gagner un temps considérable.
- *je veux* ajuster chaque proposition au glisser-déposer et publier seulement quand
  je valide.
- *je veux* voir le récapitulatif d'heures (sup., absences, majorations) se mettre à
  jour en direct *afin de* préparer la paie.
- *je veux* réutiliser des modèles de semaine (A/B/C/D).

### Qualité (payant)
- *En tant que* pilote qualité, *je veux* rédiger des procédures hiérarchisées et
  versionnées *afin d'*être prêt pour l'inspection.
- *je veux* déclarer une non-conformité (mineure / majeure / critique) et suivre les
  actions correctives jusqu'à clôture.
- *je veux* savoir qui a lu quelle procédure (lecture confirmée au défilement ≥ 90 %).

### Messagerie (payant)
- *En tant que* membre de l'équipe, *je veux* échanger en interne, en temps réel, sur
  des sujets qui touchent aux patients, *avec la garantie* que les messages sont
  chiffrés au repos.

### Tâches (payant)
- *je veux* créer des tâches personnelles ou en assigner à un collègue, avec priorité,
  échéance et commentaires *afin que* rien ne se perde.

### SMS patients (payant, crédits)
- *En tant que* préparateur, *je veux* prévenir un patient qu'une commande est arrivée
  en un clic, à partir d'un modèle *afin de* gagner du temps.
- *je veux* voir en direct si le SMS a été livré ou a échoué, et être remboursé du
  crédit en cas d'échec.

### Administration SaaS
- *En tant qu'*administrateur, *je veux* gérer le catalogue de ressources officielles
  et valider les recommandations communautaires avant promotion.
- *je veux* consulter l'état des abonnements et intervenir si besoin.

## 4.3 Arborescence de navigation

```
/ (vitrine — application séparée)
│
├── /login · /register · /forgot-password · /reset-password · /verify-email
├── /onboarding                       (5 étapes)
│
└── / (coquille authentifiée : barre latérale + en-tête)
    ├── /dashboard                     Tableau de bord des raccourcis      [gratuit]
    ├── /ressources-partagees          Catalogue communautaire            [gratuit]
    ├── /planning                      Planning d'équipe                   [payant]
    ├── /quality                       Procédures (tableau)               [payant]
    │   ├── /quality/procedures/new · /:id · /:id/edit
    │   ├── /quality/nc · /nc/new · /nc/:id
    │   └── /quality/archives
    ├── /taches                        Tâches (kanban)                    [payant]
    ├── /messagerie                    Messagerie d'équipe                [payant]
    ├── /sms · /sms/settings           SMS patients                      [payant]
    └── /account                       Compte, équipe, facturation        [gratuit]

/admin/**                              Back-office SaaS (bloc isolé, lazy-loadé)
```

Les routes `[payant]` portent le guard `paidAccessGuard` ; certaines actions
(création de procédure, gestion du planning, assignation de tâche) portent en plus un
guard de rôle. Détail : [chapitre 05](05-frontend-angular.md).

## 4.4 Charte graphique

| Élément | Valeur |
|---|---|
| Couleur primaire | **vert `#15803d`** (`green-700`) |
| Déclinaisons | `green-600 #16a34a`, `green-50 #f0fdf4`, `green-100`, `green-200` |
| Accent « partenaire » | `emerald` (`#059669`) |
| Bleu | **réservé** aux données collaborateurs (avatars, identité) — proscrit ailleurs |
| Icône de catégorie | 📂 fixe (le champ icône a été retiré du modèle) |
| Typographie | pile système (`system-ui`) |
| Impression | feuille `@media print` dédiée, format A4 paysage pour plannings et procédures |

Le vert est un choix identitaire (univers santé / pharmacie, la croix verte) et un
choix d'accessibilité (contraste suffisant sur fond clair).

## 4.5 Schéma fonctionnel — enchaînement des vues

> **[À PRODUIRE — exigence `Cr 4.a.4`]**
>
> Le critère demande un schéma décrivant **en détail l'enchaînement des vues en
> fonction des différentes actions et interactions**. L'arborescence du §4.3 donne la
> structure, mais pas les transitions.
>
> À formaliser : le parcours d'authentification (login → onboarding si incomplet →
> tableau de bord ; 401 → *refresh* → rejeu ; 402 → facturation), la session
> collaborateur par PIN, et un parcours métier complet (composition puis publication
> d'un planning, ou déclaration puis clôture d'une non-conformité).

## 4.6 Maquettes et captures

> **[À COMPLÉTER par le porteur du projet]**
>
> Le maquettage relève du **bloc 4 (option UX-UI)**, qui n'est pas l'option retenue —
> il n'y a donc pas de wireframes ni de brand board à produire. Mais `Cr 1.a.1`
> (« l'intégration est conforme à la maquette ») suppose un référentiel visuel.
>
> Deux options :
> - **Si des maquettes existent** (Figma, Penpot, croquis) : les intégrer ici (export
>   PNG dans `docs/assets/`), en indiquant l'outil et le lien du projet source.
> - **Sinon** : documenter l'interface **telle qu'implémentée**, par des captures
>   annotées des écrans clés (tableau de bord dans ses 3 vues, planning semaine,
>   éditeur de procédure, messagerie, parcours d'onboarding), et expliquer à l'oral
>   que la conception visuelle a été menée directement en intégration.
