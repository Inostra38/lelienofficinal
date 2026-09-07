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

## 12.4 Incohérences de nommage / documentation

| Point | Réalité | Action |
|---|---|---|
| « SMS OVH » dans la mémoire projet et `fichiers MD/TESTS.md` | le fournisseur réel est **SMS Partner** (`api.smspartner.fr`) | corriger les mentions ; cette documentation fait foi |
| « Angular 18 » dans d'anciennes notes | le code est en **Angular 20.2** | idem |
| Domaine `lelienofficinal.fr` dans certains commentaires | le domaine réel est `lienofficinal.fr` (app) / `www.lienofficinal.fr` (vitrine) | uniformiser |

## 12.5 Dette — fonctionnelle

- **Moteur de paie analytique** (`apps/planning/paye_analytics.py`) : logique riche
  (fériés, TNS, heures sup, snapshots contractuels), bien testée unitairement, mais
  **non validée sur des bulletins réels**. À confronter au terrain avant toute
  utilisation en production comme source de vérité RH.
- **App `notifications`** : présente mais désactivée dans `INSTALLED_APPS`.
- **Recommandation communautaire** : chaîne complète (proposition → validation admin
  → promotion) implémentée mais peu éprouvée faute d'utilisateurs.
- **Tests e2e** : absents (front comme back au niveau parcours complet navigateur).

## 12.6 Perspectives

### Court terme (avant test utilisateur réel)
1. Corriger les points bloquants du §12.2 (gate backend, `ng test` en CI).
2. Basculer Stripe en `pk_live_` / clés de production, valider le webhook en conditions réelles.
3. `.env.example` + court guide de contribution.

### Moyen terme (avant exploitation commerciale)
4. **Hébergement certifié HDS** (données de santé) — prérequis réglementaire.
5. Validation terrain du moteur de paie sur un panel d'officines.
6. Montée en couverture de tests selon `fichiers MD/TESTS.md` (P1 → P3), ajout d'e2e.
7. Extraire `beat` dans son propre process pour pouvoir scaler le worker.
8. Supervision : activer Sentry en prod, ajouter des métriques (temps de réponse, file Celery).

### Long terme
9. Projet annexe **« carte marché »** (étude géographique des 20 003 officines,
   MapLibre + DuckDB) : aujourd'hui **hors application**, envisagé en phase 2 comme
   module Django/Angular pour la prospection.
10. Réactiver / repenser l'app `notifications` (centre de notifications unifié).
11. Réévaluer l'opportunité du SSR pour le référencement de pages publiques.
