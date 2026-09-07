# 11 — Tests & qualité

> **Référentiel :** **`C4.g`** (`Cr 4.g.2` — *« des tests unitaires sont réalisés et
> validés »*, `Cr 4.g.3`, `Cr 4.g.4`) · **`C5.c`** (`Cr 5.c.2`, `Cr 5.c.3` — erreurs de
> développement identifiées, outils de débogage maîtrisés).
> Détail en [annexe](annexe-referentiel-competences.md).

## 11.1 Backend — Django `TestCase`

- **Framework** : `unittest` / `django.test.TestCase` lancé par `manage.py test`.
  Pas de `pytest`, pas de `factory_boy` — les jeux de données sont construits dans
  les `setUp`.
- **Réglages de test** : `backend_lien_officinal/settings_test.py` = `from .settings import *`
  puis SQLite en mémoire, cache factice (désactive le *throttling*), cache
  `admin_revocation` fonctionnel en LocMem, redirection HTTPS neutralisée
  (sinon chaque requête de test renverrait 301 en CI).
- **~52 modules de tests** sous `apps/*/tests/` et `tests/`.

### Domaines couverts

| Zone | Modules notables |
|---|---|
| Paie / planning | `test_paye_analytics*` (×7), `test_calculator`, `test_performance` (contrôles N+1 via `assertNumQueries`), `test_views_shifts/absences/templates/security` |
| Facturation | `test_api`, `test_webhook`, `test_tasks`, `test_promo`, `test_pdf`, **`test_free_tier`** (verrouille la frontière gratuit/payant), `test_confirm_replay` (anti-rejeu de souscription) |
| Auth & sécurité | `test_auth`, `test_hardening_20260710`, `test_audit_idor_20260709`, `test_audit_majeurs_20260709`, `test_account_deletion*` (×3) |
| Admin | `test_auth`, `test_revocation_failclosed` |
| Isolation multi-tenant | `tests/test_isolation.py` |
| WebSocket (*handshake*) | `test_ws_sms_handshake`, `apps/quality/tests/test_ws_handshake`, `apps/tasks/tests/test_ws_handshake` |
| Intégration bout-en-bout | `tests/integration/` — onboarding, planning, absences, qualité, SMS |

### Exécution

- Local : `make test` (liste `TESTS` dans `backend_lien_officinal/Makefile`).
- CI : liste équivalente dans `.github/workflows/ci.yml`.

> ⚠️ **La liste des modules est maintenue à la main, en double.** La disposition
> `apps/` sur le `sys.path` empêche la découverte automatique par `manage.py test`
> sans argument. Voir [chapitre 12](12-limites-dette-roadmap.md).

## 11.2 Frontend — Karma + Jasmine

- **14 fichiers `.spec.ts`** : `AuthService`, `authGuard`, `planningManagerGuard`,
  `CollaboratorService`, `PlanningService`, composants du tableau de bord
  (`sidebar`, `header`, `card-detail`), modales (`pin-pad`, `add-link-modal`,
  `category-assigner-modal`, `ad-space`).
- Lancement : `ng test` (ou `make test-front` en `ChromeHeadless`).
- **Pas de tests end-to-end** (Cypress / Playwright absents).

> ⚠️ Le job CI « Tests & Build Angular » **compile mais n'exécute pas** `ng test`.

## 11.3 Analyse statique et style

| Outil | Portée | Configuration |
|---|---|---|
| **flake8** | backend (`apps/`) | `make lint` — `--max-line-length=120 --exclude=migrations` |
| **Prettier** | frontend | configuration *inline* dans `package.json` (`printWidth: 100`, `singleQuote: true`) |
| **ESLint** | — | **non configuré** (dette identifiée) |
| **TypeScript strict** | frontend | `strict`, `strictTemplates`, `noImplicitOverride`, `noImplicitReturns`… |

## 11.4 Sécurité automatisée

- **OWASP ZAP baseline** hebdomadaire (`.github/workflows/zap-scan.yml`) — voir
  [chapitre 10](10-deploiement-exploitation.md).
- **Dependabot** — mises à jour hebdomadaires `pip` / `npm` / `github-actions`.
- **Tests de non-régression de sécurité datés** — chaque revue de sécurité laisse un
  module `test_*_20260709.py` / `test_hardening_20260710.py` qui fige le comportement
  corrigé (voir [chapitre 08](08-securite-conformite.md)).

## 11.5 Plan de test de référence

Le fichier `fichiers MD/TESTS.md` (à la racine du dépôt) tient une **batterie de tests
priorisée P1/P2/P3**, backend et frontend, avec pour chaque cas la cible et le fichier
de test associé, et un marquage ✅ fait / ☐ à faire. C'est la feuille de route de la
montée en couverture.

## 11.6 Limite structurelle

Le projet est au **stade MVP et n'a jamais été testé en conditions réelles par un
utilisateur**. La couverture est solide sur les zones à risque (paie, facturation,
isolation, auth) mais partielle ailleurs (UI, parcours complets). Voir
[chapitre 12](12-limites-dette-roadmap.md).
