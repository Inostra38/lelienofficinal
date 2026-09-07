# Annexe A1 — Correspondance avec le référentiel de compétences

Titre professionnel **Développeur Web**. Le titre s'obtient en validant le **tronc
commun (bloc 1 + bloc 2)**, **un bloc optionnel** et une **période de stage**.

**Option retenue : bloc 3 — Développement avancé avec un framework.**

## ⚠️ Deux projets sont présentés

| Bloc | Projet présenté |
|---|---|
| **Bloc 1 — Front End** | **Site Pharmacie Nord Montargis** — `pharmacienordmontargis.fr` (dépôt séparé) |
| **Bloc 2 — Back End** | **Le Lien Officinal** — objet de cette documentation |
| **Bloc 3 — Framework** | **Le Lien Officinal** (Angular + Django) |

Le bloc 1 est porté par un second projet parce qu'il évalue des choses qu'une
application Angular derrière authentification ne permet pas de démontrer : un HTML
**réellement validable au W3C** (un SPA compilé émet des attributs générés), un site
**public indexable** pour le référencement, et du **JavaScript natif** — le référentiel
demande explicitement la maîtrise des « fonctions natives du langage » et de la
manipulation du DOM, que justement un framework masque.

Légende de couverture :
**✅ couvert** · **◐ partiel / à argumenter à l'oral** · **⚠️ écart assumé**
(les écarts sont détaillés au [chapitre 12](12-limites-dette-roadmap.md)).

---

## Bloc 1 — Développement Front End

> **Projet : site Pharmacie Nord Montargis.** 6 pages HTML statiques (accueil,
> catalogue, validation de commande, dépôt sécurisé d'ordonnance, mentions légales,
> politique de confidentialité), Tailwind CSS + 4 feuilles thématiques,
> **3 395 lignes de JavaScript natif** en 11 modules, aucun framework front.
> API Express en appui, hors périmètre de ce bloc.
>
> État constaté le 2026-09-07. Les écarts sont **documentés, non corrigés** — choix assumé.

### Activité 1 — Traduction de la maquette en code

| Compétence | Couverture | Où / comment |
|---|---|---|
| **C1.a** Intégrer les maquettes en HTML/CSS | ✅ | 6 pages en **HTML statique**, donc `Cr 1.a.3` **réellement validable au W3C** — contrairement à un SPA compilé. `Cr 1.a.4` code commenté et indenté ; modules JS documentés, CSS séparé par thématique. |
| **C1.b** Responsive et compatibilité navigateurs | ✅ | `Cr 1.b.1` **156 classes de point de rupture** Tailwind (`sm:` `md:` `lg:` `xl:`) sur les 6 pages. `Cr 1.b.2` PostCSS + autoprefixer sur toute la chaîne de build. |
| **C1.c** Accessibilité (RGAA) | ◐ | Bien travaillée : `Cr 1.c.1` **101 attributs `aria-`**, 12 `role`, **5 `alt` pour 5 images** (100 %), 15 `label`. `Cr 1.c.3` ✅ information jamais portée par la seule couleur. `Cr 1.c.4` éléments natifs focusables, formulaires étiquetés. **Seul écart : `Cr 1.c.2`, la police adaptée aux dyslexiques, absente.** |
| **C1.d** Intégration réutilisable, organisée, synthétique | ✅ | Approche utilitaire **Tailwind** (`Cr 1.d.1` classes génériques, `Cr 1.d.4` pas de répétition) + `tailwind.config.js`. `Cr 1.d.2`/`Cr 1.d.3` CSS custom découpé par rôle : mode clair, bandeau cookies, pages légales. |
| **C1.e** Référencement naturel | ◐ | **Site public indexable.** Acquis : `Cr 1.e.1` un `h1`, 11 `h2`, 12 `h3` · `Cr 1.e.5` `title` + `meta description` par page · `Cr 1.e.7` 5 `alt` pour 5 images · `Cr 1.e.9` favicon · `og:` complet (titre, description, image, url, type, locale) · `robots.txt`. **Écarts : `Cr 1.e.6` pages canoniques absentes · `Cr 1.e.3` balisage schema.org absent · `Cr 1.e.10` `sitemap.xml` référencé mais inexistant · `Cr 1.e.4` `nav`/`main`/`section` présents mais pas `header`/`footer`/`article`/`aside`.** |

### Activité 2 — Développement de fonctionnalités front end

| Compétence | Couverture | Où / comment |
|---|---|---|
| **C2.a** Interactivité et animations JavaScript | ✅✅ | **3 395 lignes de JavaScript natif**, 11 modules (`script`, `api`, `cart-v2`, `catalogue`, `home`, `upload`, `validation`, `csrf-manager`, `cache-manager`, `cookie-config`, `config`). `Cr 2.a.2` manipulation directe du DOM : 40 `classList`, 11 `querySelector`. `Cr 2.a.3`/`Cr 2.a.4` 10 blocs `@keyframes`, 45 transitions CSS, un `IntersectionObserver`. **`Cr 2.a.5` les trois paradigmes** : orienté objet (`csrf-manager`, `cache-manager`, `api`), fonctionnel (transformations du catalogue et du panier), événementiel (**33 `addEventListener`**). |
| **C2.b** Validation des saisies utilisateur | ◐ | `validation.js` (207 lignes) côté client et `express-validator` + `validation.middleware.js` côté serveur ; 15 `label` et attributs `required`. **`Cr 2.b.1` (contrôle en temps réel pendant la saisie) est le point le plus perfectible** — à savoir montrer, ou à reconnaître. |
| **C2.c** Requêtes asynchrones avec le serveur | ✅✅ | `Cr 2.c.1` **57 `await`, 37 `async`, 6 `fetch`**. `Cr 2.c.4` **erreurs traitées sans interrompre le script** : `try`/`catch`, `throw`, contrôle du statut HTTP dans `api.js`. `Cr 2.c.2` **`csrf-manager.js`** — jeton anti-CSRF sur chaque appel mutant, ce qui compte d'autant plus que le site reçoit des **dépôts d'ordonnances** (données de santé). `cache-manager.js` en complément. |
| **C2.d** Librairies externes | ✅ | `Cr 2.d.1` Tailwind CSS et PostCSS, choisis et configurés pour un besoin précis ; pas de dépendance superflue. `Cr 2.d.2` intégration conforme à la documentation (`tailwind.config.js`, `postcss.config.js`). |


## Bloc 2 — Développement Back End

### Activité 3 — Data : analyse, modélisation, traitement

| Compétence | Couverture | Où / comment |
|---|---|---|
| **C3.a** Synthétiser et formaliser le modèle de données | ✅ | [Chapitre 07](07-modele-de-donnees.md) : **quatre diagrammes entité-association** (cœur/facturation, ressources, planning, qualité), sources dans `docs/diagrams/`. **`Cr 3.a.3` ✅ des informations externes provenant d'API alimentent le modèle** : Stripe (`Subscription`, `Invoice`, `SmsCreditTransaction`), SMS Partner (`SMSLog`, statuts de livraison par webhook), API Anthropic (modèles de planning générés). |
| **C3.b** Construire la base de données | ✅ | `Cr 3.b.1` nommage cohérent (`owner_pharmacy`, `pin_hash`, `trial_ends_at`). `Cr 3.b.2` types adaptés : `DecimalField` pour les montants et les heures contractuelles, `PositiveIntegerField` pour les crédits, `UUIDField` en clé primaire des messages, `TextChoices` pour les énumérations. `Cr 3.b.3` relations : `ForeignKey`, `OneToOneField` (abonnement), `ManyToManyField` (pilotes de procédure), avec `on_delete` choisi cas par cas (`PROTECT` sur les factures, `SET_NULL` + instantané sur les shifts). **66 migrations** versionnées. |
| **C3.c** Interroger la base par un langage de requêtes | ◐ | `Cr 3.c.1` CRUD complet via l'**ORM Django**. `Cr 3.c.2` tri et filtres (`.filter()`, `.exclude()`, `.order_by()`, `Q()`, `F()`). `Cr 3.c.3` clés étrangères et jointures optimisées : `select_related`, `prefetch_related`, `Prefetch('adopted_preferences')`, plus des tests `assertNumQueries` qui verrouillent l'absence de N+1 (`apps/planning/tests/test_performance.py`). **À argumenter à l'oral** : l'ORM génère le SQL, savoir l'afficher (`queryset.query`) et le commenter — le référentiel cite explicitement SQL. |
| **C3.d** Respecter le cadre légal (RGPD) | ✅✅ | `Cr 3.d.1` **données sensibles identifiées** : la messagerie véhicule des données de santé, ce qui a dicté l'hébergement en France et le chiffrement au repos. `Cr 3.d.2` information de l'utilisateur : page **Politique de confidentialité** + CGU/CGV sur la vitrine. `Cr 3.d.3` droits : consultation et modification du profil dans l'espace compte, **droit à l'effacement** par suppression différée et annulable, exécutée par une tâche planifiée nocturne avec anonymisation (`apps/core/account_deletion.py`, `execute_scheduled_deletions`), y compris l'effacement des PII côté Stripe. `Cr 3.d.4` **données protégées** : chiffrement Fernet au repos (contenu des messages, secret TOTP), numéros de téléphone stockés en SHA-256 uniquement, purge à 30 jours des journaux SMS, supervision Sentry configurée pour ne jamais capturer de contenu déchiffré. Voir [ch. 08](08-securite-conformite.md). |

### Activité 4 — Développement de fonctionnalités back end

| Compétence | Couverture | Où / comment |
|---|---|---|
| **C4.a** Conceptualiser, formaliser le schéma fonctionnel | ◐ | [Chapitre 04](04-specifications-fonctionnelles.md) : acteurs, user stories par module, **arborescence de navigation** avec les périmètres gratuit/payant. `Cr 4.a.4` demande l'**enchaînement des vues en fonction des actions** — l'arborescence en tient lieu ; un diagramme d'enchaînement dédié reste à produire (voir [ch. 12](12-limites-dette-roadmap.md)). |
| **C4.b** Développer avec un langage serveur | ✅ | Python 3.12 / Django 6. `Cr 4.b.2` code indenté (flake8, ligne 120) et **abondamment commenté** — les commentaires expliquent le *pourquoi*, pas le *quoi*. `Cr 4.b.3` organisation en 10 applications métier sous `apps/`. `Cr 4.b.4` conventions de nommage Django respectées. `Cr 4.b.5` **limites du code connues et documentées** ([ch. 12](12-limites-dette-roadmap.md)). `Cr 4.b.6` erreurs traitées : exceptions DRF typées, `retry` Celery, cache résilient. |
| **C4.c** Programmation orientée objet et héritage | ✅ | `Cr 4.c.2` héritages réels et structurants : `Pharmacy(AbstractBaseUser, PermissionsMixin)`, `PharmacyManager(BaseUserManager)`, `HasPaidAccess(BasePermission)`, `PaymentRequired(APIException)`, `SMSTemplateViewSet(ModelViewSet)`, `ConversationConsumer(AsyncWebsocketConsumer)`, `ResilientRedisCache`. `Cr 4.c.1` portée cohérente : attributs privés préfixés `_`, `@property` calculées (`is_access_allowed`, `grace_days_left`), `@classmethod` de fabrique (`Invoice.create_with_sequential_number`). `Cr 4.c.3` **namespaces** = packages Python, **autoloader** = système d'import ; `apps/` ajouté au `sys.path` dans la configuration. |
| **C4.d** Architecture MVC | ◐ | Django implémente le patron sous le nom **MTV** — même séparation, vocabulaire différent, à expliciter à l'oral : `Cr 4.d.1` le **modèle** (`apps/*/models.py`) porte les interactions avec la base ; `Cr 4.d.2` le **contrôleur** (`views.py` + `serializers.py`) implémente la logique et prépare les données ; `Cr 4.d.3` la **vue** est la représentation JSON consommée et rendue par les composants Angular. Le front applique lui-même une séparation équivalente (composant / template / service). |
| **C4.e** Identifier l'utilisateur et délimiter ses champs d'action | ✅✅ | `Cr 4.e.1` **intégrité des données protégée** : requêtes paramétrées par l'ORM (pas d'injection SQL), assainissement DOMPurify du HTML, validation partagée des téléversements (`apps/core/upload_validation.py`), CSP stricte. `Cr 4.e.2` authentification par identifiant unique (e-mail) + mot de passe, **système de jetons** JWT (accès en mémoire, *refresh* en cookie HttpOnly avec rotation et liste noire). `Cr 4.e.3` **délimitation des actions par rôle** : 8 permissions fonctionnelles par collaborateur, rôle Titulaire inaltérable, permissions DRF au niveau objet (pilote d'une procédure), et un **back-office administrateur totalement séparé** (secret de signature distinct, 2FA TOTP, liste blanche d'IP). Voir [ch. 08](08-securite-conformite.md). |
| **C4.f** Travailler en équipe, gestion des versions | ◐ | `Cr 4.f.2` ✅ **outil collaboratif maîtrisé** : GitHub, branche par sujet, *pull requests* systématiques (jamais de commit direct sur `main`), Conventional Commits, revue des PR Dependabot, CI bloquante. `Cr 4.f.3` ✅ auto-évaluation avant contribution : la CI teste toute branche poussée. **`Cr 4.f.1` et `Cr 4.f.4` (collaboration, participation au travail collectif) ne peuvent pas être démontrés sur ce projet, développé en solo** — ils relèvent de la période de stage en entreprise. |
| **C4.g** Préparer l'application pour la livraison | ◐ | `Cr 4.g.1` conformité fonctionnelle vérifiée module par module. `Cr 4.g.2` ✅ **tests unitaires réalisés et validés** : ~52 modules Django, exécutés en CI sur chaque *push* ([ch. 11](11-tests-qualite.md)). `Cr 4.g.3`/`Cr 4.g.4` application **déployée et fonctionnelle en production**, mais **pas encore éprouvée par un utilisateur réel** — c'est l'étape suivante, assumée comme telle. |

---

## Bloc 3 (option) — Développement avancé avec un framework

| Compétence | Couverture | Où / comment |
|---|---|---|
| **C5.a** S'approprier l'architecture et les fonctionnalités d'un framework | ✅✅ | **Deux frameworks, front et back** : Angular 20 (composants standalone, injection de dépendances, routing avec guards, intercepteurs, RxJS et signaux) et Django 6 / DRF (ORM, migrations, middlewares, sérialiseurs, permissions, *throttling*, Channels, Celery). `Cr 5.a.1` bases solides en TypeScript et Python. `Cr 5.a.2`/`Cr 5.a.3` spécificités maîtrisées et expliquées tout au long des [chapitres 05](05-frontend-angular.md) et [06](06-backend-django.md). |
| **C5.b** Configurer le framework et ses dépendances | ✅ | `Cr 5.b.1` **gestionnaires de dépendances** : npm (`package.json`, `package-lock.json`) et pip (`requirements.txt`), choix justifiés dépendance par dépendance ([ch. 05 §5.1](05-frontend-angular.md), [ch. 06 §6.1](06-backend-django.md)). `Cr 5.b.2` compatibilité des versions maintenue par **Dependabot** hebdomadaire + CI. **`Cr 5.b.3` ✅✅ variables d'environnement correctement renseignées** : configuration entièrement pilotée par l'environnement, avec des **garde-fous au démarrage** qui refusent de booter si un secret est faible ou absent ([ch. 06 §6.2](06-backend-django.md)) ; inventaire complet des variables au [ch. 10 §10.5](10-deploiement-exploitation.md). |
| **C5.c** Développer une application évolutive avec un framework | ✅ | `Cr 5.c.1` solutions du framework adaptées plutôt que contournées : permission DRF sur mesure renvoyant un **402**, backend de cache résilient, `ControlValueAccessor` maison pour encapsuler des librairies tierces, middleware CSP. `Cr 5.c.2`/`Cr 5.c.3` **débogage outillé** : Sentry en production (configuré pour ne pas capturer de données de santé), journalisation par application, DevTools et *source maps* en développement, tests `assertNumQueries` pour traquer les requêtes N+1. `Cr 5.c.4` application livrée et fonctionnelle, déployée en continu ([ch. 10](10-deploiement-exploitation.md)). |

---

## Points à préparer pour la soutenance

Le jury peut demander des **modifications de code en direct** et une argumentation
serrée. Quatre sujets méritent une préparation spécifique :

1. **SQL derrière l'ORM** (`C3.c`) — savoir afficher le SQL généré par un *queryset*
   (`str(queryset.query)`), expliquer une jointure `select_related` et justifier le
   choix de l'ORM (requêtes paramétrées, donc pas d'injection).
2. **MVC vs MTV** (`C4.d`) — expliquer la correspondance sans esquiver la question de
   vocabulaire.
3. **Écarts du bloc 1** (`C1.e`, `C1.c`, `C2.b`) — canonique, schema.org, sitemap,
   balises sémantiques, police dyslexique, validation en temps réel. Les annoncer avec
   leur chiffrage (~2 h 30 au total) plutôt que les laisser découvrir au jury.
4. **Travail collectif** (`C4.f`) — préparer ce qui sera présenté depuis la période de
   stage, puisque ce projet est solo.
