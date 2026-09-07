# Annexe A1 — Correspondance avec le référentiel DWWM

Titre professionnel **Développeur Web et Web Mobile** (RNCP niveau 5). Deux
activités-types, chacune exigeant une application **sécurisée**.

> ⚠️ **CP4** et **CP8** portent sur une **solution de gestion de contenu (CMS) ou
> e-commerce** (type WordPress / PrestaShop). Le Lien Officinal est une application
> sur mesure sans CMS : ces deux compétences se démontrent généralement sur un
> **projet CMS distinct** dans le cadre de la formation. Le tableau ci-dessous couvre
> CP1–CP3 et CP5–CP7.

## Activité-type 1 — Front-end sécurisé

| CP | Intitulé | Où c'est démontré | Fichiers de référence |
|---|---|---|---|
| **CP1** | Maquetter une application | [Ch. 04](04-specifications-fonctionnelles.md) — acteurs, user stories, arborescence de navigation (§4.3), charte graphique (§4.4), maquettes (§4.5) | `docs/04-specifications-fonctionnelles.md` |
| **CP2** | Réaliser une interface utilisateur web statique et adaptable | [Ch. 05 §5.6](05-frontend-angular.md#56-interface-utilisateur) — Tailwind, responsive (points de rupture Tailwind + `@HostListener('window:resize')`), feuille `@media print` A4, palette et charte | `frontend-lien-officinal/src/styles.css`, `tailwind.config.js`, `src/app/features/dashboard/*` |
| **CP3** | Développer une interface utilisateur web dynamique | [Ch. 05](05-frontend-angular.md) en entier — composants Angular standalone, routing + guards (§5.3), intercepteur HTTP (§5.4), gestion d'état RxJS + signaux (§5.5), consommation d'API REST, **temps réel WebSocket** (§5.7), formulaires réactifs et template-driven | `src/app/core/auth/auth.interceptor.ts`, `src/app/core/auth/auth.guard.ts`, `src/app/core/services/subscription-state.service.ts`, `src/app/features/dashboard/dashboard.component.ts`, `src/app/core/services/messaging.service.ts` |
| Sécurité front | — | [Ch. 08 §8.2, §8.5](08-securite-conformite.md) — jeton d'accès **en mémoire**, *refresh* en cookie HttpOnly, jeton attaché **uniquement** à notre API (anti-exfiltration `C04/C05`), assainissement **DOMPurify** de tout HTML riche (`C4`), SRI activé au build | `src/app/core/auth/auth.service.ts`, `src/app/core/utils/html-sanitizer.ts`, `angular.json` |

## Activité-type 2 — Back-end sécurisé

| CP | Intitulé | Où c'est démontré | Fichiers de référence |
|---|---|---|---|
| **CP5** | Créer une base de données | [Ch. 07](07-modele-de-donnees.md) — modélisation entité-association (4 diagrammes), multi-tenant, overlay `PharmacyPreference`, `CheckConstraint` et index partiels PostgreSQL, 66 migrations | `backend_lien_officinal/apps/*/models.py`, `apps/*/migrations/` |
| **CP6** | Développer les composants d'accès aux données | [Ch. 06 §6.4](06-backend-django.md#64-api-rest) — ORM Django, sérialiseurs DRF, `get_queryset` filtré par tenant, `perform_create` qui force le propriétaire, `select_for_update` pour la numérotation de facture (`C19`), `F()` pour le débit atomique de crédits | `apps/core/views_sms.py`, `apps/billing/models.py:204`, `apps/resources/views.py` |
| **CP7** | Développer la partie back-end d'une application web sécurisée | [Ch. 06](06-backend-django.md) + [Ch. 09](09-modules-transverses.md) — API REST (ViewSets + APIView), **authentification JWT** double (SimpleJWT + JWT admin maison), **permissions** (`IsAuthenticated`, `HasPaidAccess` → 402, permissions qualité niveau objet), **throttling** DRF + classes dédiées, **tâches asynchrones Celery**, WebSocket Channels, webhooks Stripe / SMS signés | `apps/billing/permissions.py`, `apps/core/tasks.py`, `apps/messaging/consumers.py`, `apps/billing/views.py`, `backend_lien_officinal/settings.py:329` |
| Sécurité back | — | [Ch. 08](08-securite-conformite.md) en entier — garde-fous au démarrage (`C3`, `E1`), verrou PIN anti-force-brute (`E4`), chiffrement au repos + rotation de clés (`E5`), IP whitelist + 2FA TOTP admin, CSP, RGPD (effacement différé, hachage des numéros, purge 30 j), OWASP ZAP hebdo, tests de non-régression datés | `backend_lien_officinal/settings.py`, `apps/team/models.py:123`, `apps/admin_panel/`, `apps/core/tasks.py` |

## Compétences transverses attendues au jury

| Attendu | Couverture |
|---|---|
| Gestion de projet | [Ch. 02](02-gestion-de-projet.md) — workflow Git par *pull request*, Conventional Commits, CI/CD, registre de dette |
| Veille & sécurité | [Ch. 08](08-securite-conformite.md), [Ch. 11 §11.4](11-tests-qualite.md#114-sécurité-automatisée) — Dependabot, ZAP, revues d'audit successives |
| Tests | [Ch. 11](11-tests-qualite.md) — ~52 modules backend, 14 specs front, plan priorisé `TESTS.md` |
| Déploiement / mise en production | [Ch. 10](10-deploiement-exploitation.md) — Scalingo, pipeline GitHub Actions |
| Accessibilité & éco-conception | [Ch. 12](12-limites-dette-roadmap.md) — points d'amélioration identifiés |
| Environnement anglophone | Terminologie technique, dépendances et outillage en anglais ; documentation projet en français |
