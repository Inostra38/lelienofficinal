# 12 — Limites, dette technique & perspectives

Ce chapitre est volontairement **transparent**. Les points ci-dessous sont des choix
conscients de priorisation au stade MVP, chacun assorti de son plan de correction.

## 12.1 Stade du projet

Le Lien Officinal est un **MVP qui n'a pas encore été testé en conditions réelles**
par une officine. La stratégie assumée : **faire tester l'application en priorité**,
et différer le durcissement structurel et la validation terrain du moteur de paie à
la fin du MVP. Cela explique plusieurs des points suivants.

## 12.2 Dette — CI/CD

| Point | Risque | Correction prévue |
|---|---|---|
| `deploy` ne dépend que de `test-and-build-frontend`, pas de `test-backend` | un backend cassé mais compilable côté front peut partir en prod | ajouter `test-backend` dans `needs:` du job `deploy` |
| `git push scalingo main --force` | écrase l'historique distant Scalingo ; un rollback par `git` devient impossible | passer à un push non forcé + déploiement via l'API Scalingo |
| Le job « Tests & Build Angular » ne lance pas `ng test` | régression front non détectée | ajouter une étape `ng test --watch=false --browsers=ChromeHeadless` |
| Liste des ~55 modules de tests backend maintenue **à la main** dans `ci.yml` **et** `Makefile` | un test ajouté mais non listé n'est jamais exécuté | script unique générant la liste, ou réorganisation permettant `manage.py test` sans argument |
| Phase `release:` du Procfile non exécutée par Scalingo | migrations appliquées « à la main » via la CI ; oubli possible | investiguer la config Scalingo (type de conteneur release) ou garder le `scalingo run migrate` mais le rendre bloquant/vérifié |

## 12.3 Dette — configuration

| Point | Détail | Correction |
|---|---|---|
| Clé Stripe `pk_test_` en production | `environment.prod.ts` embarque une clé **de test** (commentaire « passer en `pk_live_` pour la vraie prod ») | injecter la clé publique via une variable au build, basculer en `pk_live_` avant exploitation |
| Pas de `.env.example` | l'onboarding d'un nouveau dev repose sur la lecture de `settings.py` | créer `.env.example` documenté (sans valeurs) |
| `env/` (venv Windows) à la racine | dossier mort, `gitignore` mais présent sur le disque | supprimer |
| SSR Angular échafaudé mais désactivé | code `@angular/ssr` / `server.ts` non utilisé, sert un SPA statique | soit activer le SSR (SEO, temps de premier rendu), soit retirer l'échafaudage |
| Pas d'ESLint | style TS non vérifié automatiquement (au-delà de `tsc --strict`) | ajouter `@angular-eslint` |

## 12.4 Dette — accessibilité

### Le Lien Officinal — dette produit, pas écart de certification

Le bloc 1 étant présenté sur un **autre projet** (voir
[annexe](annexe-referentiel-competences.md)), l'accessibilité de cette application
n'est plus un écart au référentiel. Elle reste une **dette produit** légitime : c'est
un outil utilisé toute la journée par une équipe.

| Point | État vérifié | Correction |
|---|---|---|
| Attributs pour les lecteurs d'écran | **21** attributs `alt` ; **1 fichier sur 78** porte `aria-` / `role` / `tabindex` | `alt` sur toutes les images, `aria-label` sur les boutons-icônes, `role="dialog"` + `aria-modal` sur les modales maison, `aria-live` sur les toasts |
| Navigation au clavier | non traité systématiquement (modales, tiroirs, pavé de PIN faits maison) | piège de focus dans les modales, fermeture par `Échap`, `:focus-visible` partout, lien d'évitement |
| Police adaptée aux personnes dyslexiques | absente | police activable depuis les préférences (OpenDyslexic ou **Luciole**, conçue en France pour les déficients visuels) |
| Information non portée uniquement par la couleur | ✅ **déjà conforme** | les états (absence, brouillon, gravité d'une non-conformité) sont toujours doublés d'un libellé texte |

### Site Pharmacie Nord Montargis — les écarts du bloc 1

État constaté le 2026-09-07, **documenté et non corrigé** (choix assumé). Le socle est
bon : **101 attributs `aria-`**, 12 `role`, 100 % des images légendées, 15 `label`.

| Critère | État vérifié | Correction | Effort |
|---|---|---|---|
| `Cr 1.e.6` pages canoniques | **absentes** sur les 6 pages | une balise `<link rel="canonical">` par page | ~10 min |
| `Cr 1.e.3` balisage schema.org | **absent** | type `Pharmacy` / `LocalBusiness` : adresse, horaires, téléphone — vrai gain en référencement local | ~30 min |
| `Cr 1.e.10` plan du site | `robots.txt` référence un `sitemap.xml` **qui n'existe pas** | produire le sitemap au build | ~15 min |
| `Cr 1.e.4` sémantique des balises | `nav`, `main`, `section` présents ; pas de `header`, `footer`, `article`, `aside` | remplacer les `div` de structure | ~30 min |
| `Cr 1.c.2` police pour dyslexiques | **absente** — seul écart du critère `C1.c` | police activable, persistée par utilisateur | ~1 h |
| `Cr 2.b.1` contrôle de saisie en temps réel | perfectible — `validation.js` traite surtout l'affichage du panier | validation à la frappe sur les formulaires de commande et de dépôt d'ordonnance | ~1 h |

**Total : environ deux heures et demie** pour tout combler. Si l'écart doit être
comblé, l'ordre de priorité est : schema.org et canonical (gain réel de référencement,
et critères nommés) → sitemap → balises sémantiques → police dyslexique → validation
temps réel.

## 12.5 Écarts d'argumentation (pas de dette de code)

Trois points où le code est conforme mais où le **vocabulaire du référentiel** diffère
de celui des technologies employées. Rien à corriger, tout à savoir expliquer :

| Point | Écart | Ce qu'il faut savoir dire |
|---|---|---|
| **`C3.c` — SQL** | le référentiel cite un « langage de requêtes (SQL) » ; le projet passe **intégralement par l'ORM**, sans SQL brut | afficher le SQL généré (`str(queryset.query)`), commenter une jointure `select_related`, et justifier l'ORM : requêtes paramétrées, donc pas d'injection (`Cr 4.e.1`) |
| **`C4.d` — MVC** | Django implémente le patron sous le nom **MTV** | modèle = `models.py`, contrôleur = `views.py` + `serializers.py`, vue = la réponse JSON rendue par Angular. Même séparation, vocabulaire différent |
| **`C4.f` — travail en équipe** | projet **solo** (279 des 305 commits) | l'outillage collaboratif est maîtrisé (PR, branches, CI, revue Dependabot) ; la collaboration au sens de `Cr 4.f.1` et `Cr 4.f.4` relève de la période de stage |

Un quatrième point relève, lui, d'un livrable manquant : le **schéma fonctionnel
d'enchaînement des vues** (`Cr 4.a.4`) — voir
[chapitre 04 §4.5](04-specifications-fonctionnelles.md).

## 12.6 Incohérences de nommage / documentation

| Point | Réalité | Action |
|---|---|---|
| « SMS OVH » dans la mémoire projet et `fichiers MD/TESTS.md` | le fournisseur réel est **SMS Partner** (`api.smspartner.fr`) | corriger les mentions ; cette documentation fait foi |
| « Angular 18 » dans d'anciennes notes | le code est en **Angular 20.2** | idem |
| Domaine `lelienofficinal.fr` dans certains commentaires | le domaine réel est `lienofficinal.fr` (app) / `www.lienofficinal.fr` (vitrine) | uniformiser |

## 12.7 Dette — fonctionnelle

- **Moteur de paie analytique** (`apps/planning/paye_analytics.py`) : logique riche
  (fériés, TNS, heures sup, snapshots contractuels), bien testée unitairement, mais
  **non validée sur des bulletins réels**. À confronter au terrain avant toute
  utilisation en production comme source de vérité RH.
- **App `notifications`** : présente mais désactivée dans `INSTALLED_APPS`.
- **Recommandation communautaire** : chaîne complète (proposition → validation admin
  → promotion) implémentée mais peu éprouvée faute d'utilisateurs.
- **Tests e2e** : absents (front comme back au niveau parcours complet navigateur).

## 12.8 Perspectives

### Court terme (avant test utilisateur réel)
1. Corriger les points bloquants du §12.2 (gate backend, `ng test` en CI).
2. Basculer Stripe en `pk_live_` / clés de production, valider le webhook en conditions réelles.
3. `.env.example` + court guide de contribution.
4. **Avant la soutenance** : produire le schéma fonctionnel (`Cr 4.a.4`) et préparer
   les trois points d'argumentation du §12.5.

### Moyen terme (avant exploitation commerciale)
5. **Mise en conformité accessibilité** (§12.4) — police adaptée, `alt` / `aria`,
   navigation clavier. Au-delà du référentiel, c'est une attente légitime d'un outil
   utilisé toute la journée par une équipe.
6. **Hébergement certifié HDS** (données de santé) — prérequis réglementaire.
7. Validation terrain du moteur de paie sur un panel d'officines.
8. Montée en couverture de tests selon `fichiers MD/TESTS.md` (P1 → P3), ajout d'e2e.
9. Extraire `beat` dans son propre process pour pouvoir scaler le worker.
10. Supervision : activer Sentry en prod, ajouter des métriques (temps de réponse, file Celery).

### Long terme
11. Projet annexe **« carte marché »** (étude géographique des 20 003 officines,
    MapLibre + DuckDB) : aujourd'hui **hors application**, envisagé en phase 2 comme
    module Django/Angular pour la prospection.
12. Réactiver / repenser l'app `notifications` (centre de notifications unifié).
13. Réévaluer l'opportunité du SSR pour le référencement de pages publiques.
14. **Conteneurisation** (Docker / docker-compose) — non requise par l'option Framework
    retenue, mais elle simplifierait l'onboarding d'un développeur et la parité
    dev/prod.
