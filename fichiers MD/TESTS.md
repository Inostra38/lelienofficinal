# Batterie de tests — Le Lien Officinal (version enrichie)

> Classement par **priorité** (P1 = bloquant production, P2 = important, P3 = confort).
> Tests existants signalés ✅. À implémenter signalés ☐. **Nouveaux tests signalés 🆕.**

---

## BACKEND — Django / DRF

### P1 — Calculs métier critiques (paye, CP, fériés)

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `paye_analytics.py` | Scénario mars 2026 : heures sup TR1/TR2, absences injustifiées, ajustements | `apps/planning/tests/test_paye_analytics.py` |
| ✅ | `paye_analytics.py` | Scénario octobre 2026 : heures nuit, dimanche, CP, règle du vendredi | `apps/planning/tests/test_paye_analytics_octobre.py` |
| ✅ | `paye_analytics.py` | Mois avec un jour férié chômé (1er mai) — heures non comptées | `apps/planning/tests/test_paye_analytics_feries.py` |
| ✅ | `paye_analytics.py` | Collaborateur TNS (`is_tns=True`) — pas de calcul heures sup | `apps/planning/tests/test_paye_analytics_tns.py` |
| ✅ | `paye_analytics.py` | Cache : mois passé calculé une seule fois, retour cache au 2e appel | `apps/planning/tests/test_paye_analytics_cache.py` |
| ✅ | `paye_analytics.py` | **Collaborateur temps partiel** (24h/sem) — seuil heures sup à 24h, pas 35h | `apps/planning/tests/test_paye_analytics_edge.py` |
| ✅ | `paye_analytics.py` | **Mois sans aucun shift** — résultat vide retourné, pas d'exception | `apps/planning/tests/test_paye_analytics_edge.py` |
| ✅ | `paye_analytics.py` | **Deux absences consécutives** sur la même période — pas de doublon dans le calcul | `apps/planning/tests/test_paye_analytics_edge.py` |
| ✅ | `paye_analytics.py` | **Heures nuit chevauchant minuit** (ex: 23h → 1h) — comptage nuit correct des deux côtés de minuit | `apps/planning/tests/test_paye_analytics_edge.py` |
| ✅ | `utils.py` | `get_jours_feries()` — Pâques sur 5 ans, 1er mai, 11 novembre | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | `compute_cp_days()` — 4 combinaisons period (matin/après-midi × matin/soir), semaine avec férié | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | `parse_ai_planning_response()` — JSON valide, JSON manquant, virgule traînante, heure `8:30` sans zéro | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`get_jours_feries()` — Lundi de Pâques 2025** (21 avril) et **Ascension** (29 mai) bien présents | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`parse_ai_planning_response()` — payload avec champ inconnu** — ignoré sans exception | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`parse_ai_planning_response()` — heure invalide** (`"25:00"`) — comportement documenté | `apps/planning/tests/test_utils.py` |
| ✅ | `calculator.py` | `week_summary()` — collaborateur sans shifts, avec 1 shift, avec absence | `apps/planning/tests/test_calculator.py` |
| ✅ | `calculator.py` | `_week_summary_from_data()` — calcul heures extra 25%/50%, seuil 35h | `apps/planning/tests/test_calculator.py` |
| ✅ | `calculator.py` | **Temps partiel (24h/sem)** — seuil heures sup à 24h, pas 35h | `apps/planning/tests/test_calculator.py` |
| ✅ | `calculator.py` | **`week_summary()` — semaine avec férié ET absence** — absence_type présent, worked_h correct | `apps/planning/tests/test_calculator.py` |

---

### P1 — Sécurité & authentification

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `team/models.py` | `check_pin()` — pin correct, pin incorrect, pin vide | `apps/team/tests/test_models.py` |
| ✅ | `team/models.py` | Lockout après 50 échecs PIN — `pin_locked_until` positionné, reset après succès | `apps/team/tests/test_models.py` |
| ✅ | `team/views.py` | `login` : 200 si correct (+ JWT), 403 si incorrect, 423 si lockout | `apps/team/tests/test_views.py` |
| ✅ | `team/views.py` | `verify-pin` : 200 si correct, 403 si incorrect, 404 collab inconnu, 401 sans token | `apps/team/tests/test_views.py` |
| ✅ | `core/views.py` | Register — email déjà existant → 400, domaine normalisé en minuscule | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | Endpoints protégés sans token → 401 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **JWT forgé** (signature invalide) → 401, pas de 500 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **JWT expiré** (exp dans le passé) → 401 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **Refresh token invalide** → 401 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **Register → task Celery email déclenchée** avec le bon email et un UUID valide | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **Register → token UUID + expires enregistrés, email_verified=False** | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **verify-email token valide** → 200, email_verified=True, token effacé | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **verify-email token expiré** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **verify-email token inconnu** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **verify-email token malformé** (non-UUID) → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **resend-verification** → nouveau token différent, task Celery déclenchée | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **resend-verification email déjà vérifié** → 200 sans envoyer | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **change-email valide** → pending_email enregistré, task Celery déclenchée avec old/new email | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **change-email mauvais mot de passe** → 400, aucun envoi | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **change-email email déjà utilisé** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **change-email même email** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **confirm-email-change token valide** → email basculé, pending_email effacé, email_verified=True | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **confirm-email-change token expiré** → 400, ancien email conservé, pending_email nettoyé | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **confirm-email-change token inconnu** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **confirm-email-change token malformé** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **cancel-email-change** → pending_email effacé | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **cancel-email-change sans demande en cours** → 400 | `apps/core/tests/test_auth.py` |
| ✅ | `core/views.py` | **change-email sans auth** → 401 | `apps/core/tests/test_auth.py` |
| ✅ | `team/models.py` | Signal `ContractHistory` — `weekly_hours` mis à jour sur `Collaborator` | `apps/team/tests/test_models.py` |
| ✅ | `team/models.py` | Signal `ContractHistory` — ancien contrat fermé (end_date = start_date - 1j) | `apps/team/tests/test_models.py` |
| ✅ | `planning/views.py` | `PayeAnalyticsView` — sans collaborateur token → 403, sans `can_manage_planning` → 403 | `apps/planning/tests/test_views_security.py` |
| ✅ | `planning/views.py` | Shift d'une autre pharmacie — PATCH/DELETE/GET → 404 | `apps/planning/tests/test_views_security.py` |
| ✅ | `planning/views.py` | **Injection via query param** `?pharmacy_id=<autre_id>` — ignoré, seule la pharmacie du token utilisée | `apps/planning/tests/test_views_security.py` |
| ✅ | `planning/views.py` | **PATCH/DELETE sur ressource inexistante** → 404 | `apps/planning/tests/test_views_security.py` |

---

### P1 — Planning : logique métier views

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `planning/views.py` | `ShiftDetailView.patch()` — collision detection (409 si `updated_at` différent) | `apps/planning/tests/test_views_shifts.py` |
| ✅ | `planning/views.py` | Création shift cross-midnight — `end_datetime` = lendemain auto | `apps/planning/tests/test_views_shifts.py` |
| ✅ | `planning/views.py` | `TemplateApplyView` — semaine vide : `created=N, replaced=0` | `apps/planning/tests/test_views_templates.py` |
| ✅ | `planning/views.py` | `TemplateApplyView` — shift splitté (matin + après-midi) : les deux shifts créés | `apps/planning/tests/test_views_templates.py` |
| ✅ | `planning/views.py` | `TemplateApplyView` — absence approuvée **et pending** → shift ignoré (`absence_protected=1`) | `apps/planning/tests/test_views_templates.py` |
| ✅ | `planning/views.py` | `TemplateApplyView` — jour férié → shift ignoré (`ferie_skipped=1`) | `apps/planning/tests/test_views_templates.py` |
| ✅ | `planning/views.py` | `TemplateBulkReplaceView` — remplace tous les shifts existants, crée les nouveaux | `apps/planning/tests/test_views_templates.py` |
| ✅ | `planning/views.py` | `AbsenceListCreateView` — `working_days_count` correct (avec 1er mai, demi-journées, cheval semaines) | `apps/planning/tests/test_views_absences.py` |
| ✅ | `planning/views.py` | `PublishWeekView` — copie `collaborator_snapshot`, idempotent si déjà publiée | `apps/planning/tests/test_views_shifts.py` |
| ✅ | `planning/views.py` | `SplitShiftView` — shift coupé en deux, coupure hors plage → 400 | `apps/planning/tests/test_views_shifts.py` |

---

### P2 — Modèles : contraintes et signaux

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `planning/models.py` | `Shift.save()` — `contract_hours_snapshot` capturé à la création, non modifié ensuite | `apps/planning/tests/test_models.py` |
| ✅ | `team/models.py` | Signal `ContractHistory` — `weekly_hours` mis à jour sur `Collaborator` | `apps/team/tests/test_models.py` |
| ✅ | `team/models.py` | Signal `ContractHistory` — ancien contrat fermé (end_date = start_date - 1j) | `apps/team/tests/test_models.py` |
| ✅ | `resources/models.py` | `Category` — unicité `(pharmacy, nom)` → IntegrityError si doublon, OK autre pharmacie | `apps/resources/tests/test_models.py` |
| ✅ | `planning/models.py` | `TimeAdjustment` — `duration_minutes <= 0` → violation CheckConstraint | `apps/planning/tests/test_models.py` |
| ✅ | `resources/models.py` | **Suppression `Category`** — cascade sur ResourceCards (comportement documenté) | `apps/resources/tests/test_models.py` |

---

### P2 — Qualité : workflow NC et procédures

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `quality/views.py` | `NonConformityViewSet` — workflow OPEN→IN_PROGRESS→CLOSED, transitions invalides bloquées | `apps/quality/tests/test_nc.py` |
| ✅ | `quality/views.py` | `ProcedureViewSet` — hiérarchie parent/child, archivage parent promeut enfants en racine | `apps/quality/tests/test_procedures.py` |
| ✅ | `quality/views.py` | `ProcedureNotificationViewSet` — `is_read=False` count correct, pas de fuite inter-pharmacie | `apps/quality/tests/test_notifications.py` |
| ✅ | `quality/views.py` | `ProcedureVersion` — création version sur publish, downgrade ACTIVE→DRAFT sur PATCH | `apps/quality/tests/test_procedures.py` |
| ✅ | `quality/views.py` | **NC CLOSED → OPEN** bloqué depuis IN_PROGRESS (reopen exige CLOSED) | `apps/quality/tests/test_nc.py` |
| ✅ | `quality/views.py` | **Assign NC** avec collab d'une autre pharmacie → 404 | `apps/quality/tests/test_nc.py` |
| ☐ | `quality/views.py` | **`ProcedureVersion` — rollback** vers version précédente (endpoint non implémenté) | — |

---

### P2 — SMS et crédit

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `core/views_sms.py` | Envoi SMS — débit crédits correct, `SMSLog` créé (202) | `apps/core/tests/test_sms.py` |
| ✅ | `core/views_sms.py` | Envoi SMS — crédits insuffisants → 402, aucun `SMSLog` | `apps/core/tests/test_sms.py` |
| ✅ | `core/views_sms.py` | Webhook OVH — statut `DELIVERED`/`FAILED` mis à jour sur `SMSLog`, msgid inconnu → 200 | `apps/core/tests/test_sms.py` |
| ✅ | `core/views_sms.py` | `preview/` — GSM-7 vs Unicode : encodage détecté, comptage SMS différent | `apps/core/tests/test_sms.py` |
| ☐ | `core/views_sms.py` | **Envoi simultané** — race condition crédits (déjà `F()` atomic, pas de `select_for_update`) | — |
| ☐ | `core/views_sms.py` | **Destinataire numéro invalide** — pas de validation E.164 dans le serializer actuel | — |
| ✅ | `core/views_sms.py` | **Message vide** → 400 avant consommation de crédits | `apps/core/tests/test_sms.py` |

---

### P3 — Isolation inter-pharmacie (ownership)

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | Tous les GET | Pharmacie A ne voit pas les données de la Pharmacie B | `tests/test_isolation.py` |
| ✅ | `planning/views.py` | Shift d'une autre pharmacie — PATCH → 404 | `tests/test_isolation.py` |
| ✅ | `quality/views.py` | Procédure d'une autre pharmacie — GET → 404 | `tests/test_isolation.py` |
| ✅ | `messaging/views.py` | Message d'une autre pharmacie — GET → 404 | `tests/test_isolation.py` |
| ✅ | Tous les POST | **Création avec `pharmacy` d'une autre pharmacie dans le body** → ignoré, pharmacy du token utilisée | `tests/test_isolation.py` |
| ✅ | `team/views.py` | **Filtre `?collaborator_id=<id_autre_pharmacie>`** → résultat vide, pas 403 ni données étrangères | `tests/test_isolation.py` |
| ✅ | `planning/views.py` | **DELETE shift d'une autre pharmacie** → 404 | `tests/test_isolation.py` |

---

### 🆕 P2 — Performance & SQL

> Vérifient que l'ORM ne génère pas de requêtes N+1 et que les index critiques sont utilisés.

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `calculator.py` | **N+1 sur `pharmacy_week_summary`** — 20 collaborateurs → nombre de requêtes SQL constant (`assertNumQueries`) | `apps/planning/tests/test_performance.py` |
| ✅ | `paye_analytics.py` | **N+1 sur calcul paye** — 10 collaborateurs → nombre de requêtes SQL borné | `apps/planning/tests/test_performance.py` |
| ✅ | `planning/views.py` | **`TemplateApplyView` bulk** — 50 shifts créés en une seule transaction | `apps/planning/tests/test_performance.py` |

---

### 🆕 P2 — Tests d'intégration flux complets

> Scénarios métier de bout en bout, plus proches de la réalité d'usage.

| # | Scénario | Étapes | Fichier test |
|---|----------|--------|--------------|
| ✅ | **Flux planning complet** | Créer template → Appliquer semaine → Publier → Vérifier récap hebdo calculé | `tests/integration/test_flux_planning.py` |
| ✅ | **Flux absence + paye** | Poser absence (CP) → Approuver → Calculer paye → Vérifier jours ouvrés déduits | `tests/integration/test_flux_absences.py` |
| ✅ | **Flux onboarding pharmacie** | Créer compte → Créer collaborateur → Premier login collaborateur PIN | `tests/integration/test_flux_onboarding.py` |
| ✅ | **Flux NC qualité** | Déclarer NC → Assigner (IN_PROGRESS) → Clôturer (CLOSED) | `tests/integration/test_flux_qualite.py` |
| ✅ | **Flux SMS** | Vérifier crédits → Envoyer SMS → Vérifier débit → Simuler webhook DELIVERED | `tests/integration/test_flux_sms.py` |

---

## FRONTEND — Angular 18

### P1 — Services critiques

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `planning.service.ts` | `bulkReplaceTemplateShifts()` — POST correct, liste retournée | `planning.service.spec.ts` |
| ✅ | `planning.service.ts` | `pollGenerateTemplate()` — status `pending` puis `done` transmis tel quel | `planning.service.spec.ts` |
| ✅ | `planning.service.ts` | `updateShift()` — 409 Conflict géré et propagé | `planning.service.spec.ts` |
| ✅ | `auth.service.ts` | Token expiré → `isAuthenticated()` false, refresh invalide → erreur | `auth.service.spec.ts` |
| ✅ | `auth.service.ts` | `collaboratorLogin()` — met à jour collaboratorSubject + localStorage | `auth.service.spec.ts` |
| ✅ | `planning.service.ts` | `getPayeSummary()` — GET avec param month correct | `planning.service.spec.ts` |
| ✅ | `auth.service.ts` | **Refresh token invalide** → erreur propagée, pas de logout auto | `auth.service.spec.ts` |
| ✅ | `auth.service.ts` | **Logout** → efface tous les tokens, navigue vers /login avec returnUrl | `auth.service.spec.ts` |

---

### P2 — Composants planning

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `template-modal.component.ts` | `onTemplateGenerated()` — error handler appelé si HTTP échoue | `template-modal.component.spec.ts` |
| ☐ | `shift-drawer.component.ts` | Sauvegarde avec 409 → message "conflit" affiché | `shift-drawer.component.spec.ts` |
| ☐ | `week-view.component.ts` | Shifts cross-midnight affichés sur deux jours | `week-view.component.spec.ts` |
| ☐ | `planning-analytics.component.ts` | Chargement données — spinner pendant requête, tableau affiché | `planning-analytics.component.spec.ts` |
| 🆕 | `shift-drawer.component.ts` | **Heure fin < heure début** (sans cross-midnight) → erreur de validation affichée | `shift-drawer.component.spec.ts` |
| 🆕 | `week-view.component.ts` | **Semaine sans aucun collaborateur** → message "Aucun collaborateur" affiché | `week-view.component.spec.ts` |
| 🆕 | `week-view.component.ts` | **Navigation semaine précédente/suivante** → URL mise à jour avec la bonne date ISO | `week-view.component.spec.ts` |
| 🆕 | `planning-analytics.component.ts` | **Erreur API 500** → message d'erreur affiché, pas de spinner infini | `planning-analytics.component.spec.ts` |
| 🆕 | `absence-modal.component.ts` | **Date fin < date début** → validation bloquée | `absence-modal.component.spec.ts` |

---

### P3 — Guards et routing

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ✅ | `auth.guard.ts` | Non connecté → redirige vers `/login` avec `returnUrl` | `auth.guard.spec.ts` |
| ✅ | `auth.guard.ts` | Connecté + onboarding non terminé → redirige vers `/onboarding` | `auth.guard.spec.ts` |
| ✅ | `auth.guard.ts` | **`returnUrl` préservé** — URL initiale passée en query param | `auth.guard.spec.ts` |
| ✅ | `planning-manager.guard.ts` | Collaborateur sans `can_manage_planning` → accès refusé + toast | `planning-manager.guard.spec.ts` |
| ✅ | `planning-manager.guard.ts` | **Collaborateur avec `can_manage_planning=True`** → accès accordé | `planning-manager.guard.spec.ts` |
| ☐ | `onboarding.guard.ts` | Onboarding non complété → redirige vers `/onboarding` | `onboarding.guard.spec.ts` |

---

## Commandes pour lancer les tests

```bash
# Backend — tous les tests (découverte manuelle nécessaire car plusieurs packages)
cd backend_lien_officinal
.venv/bin/python manage.py test \
  apps.planning.tests.test_calculator apps.planning.tests.test_models \
  apps.planning.tests.test_paye_analytics apps.planning.tests.test_paye_analytics_octobre \
  apps.planning.tests.test_paye_analytics_feries apps.planning.tests.test_paye_analytics_tns \
  apps.planning.tests.test_paye_analytics_cache apps.planning.tests.test_paye_analytics_edge \
  apps.planning.tests.test_performance apps.planning.tests.test_utils \
  apps.planning.tests.test_views_absences apps.planning.tests.test_views_security \
  apps.planning.tests.test_views_shifts apps.planning.tests.test_views_templates \
  apps.quality.tests.test_nc apps.quality.tests.test_procedures \
  apps.quality.tests.test_notifications \
  apps.core.tests.test_sms apps.team.tests.test_models apps.team.tests.test_views \
  apps.resources.tests.test_models apps.admin_panel.tests.test_auth \
  tests.test_isolation \
  --settings=backend_lien_officinal.settings_test

# Backend — module spécifique
.venv/bin/python manage.py test apps.planning.tests.test_utils
.venv/bin/python manage.py test apps.planning.tests.test_views_templates

# Backend — tests d'intégration flux complets
.venv/bin/python manage.py test tests.integration

# Backend — tests de performance
.venv/bin/python manage.py test apps.planning.tests.test_performance

# Backend — avec coverage
.venv/bin/pip install coverage
.venv/bin/coverage run manage.py test
.venv/bin/coverage report --omit="*/migrations/*,*/.venv/*"
.venv/bin/coverage html  # Rapport HTML dans htmlcov/

# Frontend — tous les tests
cd frontend-lien-officinal
npm test

# Frontend — watch mode
npm test -- --watch

# Frontend — coverage
npm test -- --coverage --watch=false
```

---

## Priorités d'implémentation

| Phase | Quoi | Pourquoi |
|-------|------|----------|
| **Phase 1** | P1 calculs métier + sécurité (PIN, JWT, ownership) | Protège la donnée et la facturation |
| **Phase 2** | P1 planning views (apply template, absences, collision) | Protège l'intégrité du planning |
| **Phase 3** | 🆕 Sécurité avancée (JWT forgé, injection, refresh replay) | Vecteurs d'attaque réels en production |
| **Phase 4** | P2 qualité, SMS, modèles + 🆕 edge cases temporels | Complète la couverture MVP |
| **Phase 5** | 🆕 Tests d'intégration flux complets | Détecte les régressions inter-modules |
| **Phase 6** | 🆕 Performance N+1 + SQL | Prévient la dégradation à l'échelle |
| **Phase 7** | Frontend services + composants clés | Régression UI |
| **Phase 8** | P3 isolation + guards | Audit sécurité pré-production |
