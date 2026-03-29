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
| ☐ | `paye_analytics.py` | Mois avec un jour férié chômé (1er mai) — heures non comptées | `apps/planning/tests/test_paye_analytics_feries.py` |
| ☐ | `paye_analytics.py` | Collaborateur TNS (`is_tns=True`) — pas de calcul heures sup | `apps/planning/tests/test_paye_analytics_tns.py` |
| ☐ | `paye_analytics.py` | Cache : mois passé calculé une seule fois, retour cache au 2e appel | `apps/planning/tests/test_paye_analytics_cache.py` |
| 🆕 | `paye_analytics.py` | **Shift à cheval fin de mois** (ex: 28 fév 22h → 1er mars 6h) — heures correctement réparties entre les deux mois | `apps/planning/tests/test_paye_analytics_edge.py` |
| 🆕 | `paye_analytics.py` | **Collaborateur temps partiel** (24h/sem) — seuil heures sup à 24h, pas 35h | `apps/planning/tests/test_paye_analytics_edge.py` |
| 🆕 | `paye_analytics.py` | **Mois sans aucun shift** — résultat vide retourné, pas d'exception | `apps/planning/tests/test_paye_analytics_edge.py` |
| 🆕 | `paye_analytics.py` | **Deux absences consécutives** sur la même période — pas de doublon dans le calcul | `apps/planning/tests/test_paye_analytics_edge.py` |
| 🆕 | `paye_analytics.py` | **Heures nuit chevauchant minuit** (ex: 23h → 1h) — comptage nuit correct des deux côtés de minuit | `apps/planning/tests/test_paye_analytics_edge.py` |
| ✅ | `utils.py` | `get_jours_feries()` — Pâques sur 5 ans, 1er mai, 11 novembre | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | `compute_cp_days()` — 4 combinaisons period (matin/après-midi × matin/soir), semaine avec férié | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | `parse_ai_planning_response()` — JSON valide, JSON manquant, virgule traînante, heure `8:30` sans zéro | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`get_jours_feries()` — Lundi de Pâques 2025** (21 avril) et **Ascension** (29 mai) bien présents | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`parse_ai_planning_response()` — payload avec champ inconnu** — ignoré sans exception | `apps/planning/tests/test_utils.py` |
| ✅ | `utils.py` | **`parse_ai_planning_response()` — heure invalide** (`"25:00"`) — comportement documenté | `apps/planning/tests/test_utils.py` |
| ✅ | `calculator.py` | `week_summary()` — collaborateur sans shifts, avec 1 shift, avec absence | `apps/planning/tests/test_calculator.py` |
| ✅ | `calculator.py` | `_week_summary_from_data()` — calcul heures extra 25%/50%, seuil 35h | `apps/planning/tests/test_calculator.py` |
| ✅ | `calculator.py` | **Temps partiel (24h/sem)** — seuil heures sup à 24h, pas 35h | `apps/planning/tests/test_calculator.py` |
| ☐ | `calculator.py` | **`week_summary()` — semaine avec férié ET absence** — absence_type présent, worked_h correct | `apps/planning/tests/test_calculator.py` |

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
| ✅ | `team/models.py` | Signal `ContractHistory` — `weekly_hours` mis à jour sur `Collaborator` | `apps/team/tests/test_models.py` |
| ✅ | `team/models.py` | Signal `ContractHistory` — ancien contrat fermé (end_date = start_date - 1j) | `apps/team/tests/test_models.py` |
| ☐ | `planning/views.py` | `PayeAnalyticsView` — collaborateur sans `can_manage_planning` → 403 | `apps/planning/tests/test_views_security.py` |
| ☐ | `planning/views.py` | `TemplateBulkReplaceView` — collaborateur d'une autre pharmacie → 400 | `apps/planning/tests/test_views_security.py` |
| ☐ | `planning/views.py` | **Injection via query param** `?pharmacy_id=<autre_id>` — ignoré, seule la pharmacie du token est utilisée | `apps/planning/tests/test_views_security.py` |
| ☐ | `planning/views.py` | **PATCH sur ressource inexistante** → 404, pas de modification | `apps/planning/tests/test_views_security.py` |

---

### P1 — Planning : logique métier views

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `planning/views.py` | `ShiftDetailView.patch()` — collision detection (409 si `updated_at` différent) | `apps/planning/tests/test_views_shifts.py` |
| ☐ | `planning/views.py` | Création shift cross-midnight — `end_datetime` = lendemain auto | `apps/planning/tests/test_views_shifts.py` |
| ☐ | `planning/views.py` | `TemplateApplyView` — semaine vide : `created=N, replaced=0` | `apps/planning/tests/test_views_templates.py` |
| ☐ | `planning/views.py` | `TemplateApplyView` — shift splitté (matin + après-midi) : les deux shifts créés | `apps/planning/tests/test_views_templates.py` |
| ☐ | `planning/views.py` | `TemplateApplyView` — collaborateur en absence approuvée → shift ignoré (`absence_protected=1`) | `apps/planning/tests/test_views_templates.py` |
| ☐ | `planning/views.py` | `TemplateApplyView` — jour férié → shift ignoré (`ferie_skipped=1`) | `apps/planning/tests/test_views_templates.py` |
| ☐ | `planning/views.py` | `TemplateBulkReplaceView` — remplace tous les shifts existants, crée les nouveaux | `apps/planning/tests/test_views_templates.py` |
| ☐ | `planning/views.py` | `AbsenceListCreateView` — `working_days_count` correct pour 5 jours ouvrés avec férié | `apps/planning/tests/test_views_absences.py` |
| ☐ | `planning/views.py` | `PublishWeekView` — copie `collaborator_snapshot` au moment de la publication | `apps/planning/tests/test_views_shifts.py` |
| ☐ | `planning/views.py` | `SplitShiftView` — shift coupé en deux à l'heure donnée | `apps/planning/tests/test_views_shifts.py` |
| 🆕 | `planning/views.py` | **`TemplateApplyView` — absence en attente (non approuvée)** → shift créé quand même | `apps/planning/tests/test_views_templates.py` |
| 🆕 | `planning/views.py` | **`SplitShiftView` — heure de coupure = début ou fin du shift** → 400 | `apps/planning/tests/test_views_shifts.py` |
| 🆕 | `planning/views.py` | **`PublishWeekView` — semaine déjà publiée** → idempotent (pas d'erreur) | `apps/planning/tests/test_views_shifts.py` |
| 🆕 | `planning/views.py` | **`AbsenceListCreateView` — absence sur week-end** → `working_days_count=0` | `apps/planning/tests/test_views_absences.py` |
| 🆕 | `planning/views.py` | **`AbsenceListCreateView` — absence à cheval sur deux semaines** — `working_days_count` correct | `apps/planning/tests/test_views_absences.py` |

---

### P2 — Modèles : contraintes et signaux

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `planning/models.py` | `Shift.save()` — `contract_hours_snapshot` capturé à la création, non modifié ensuite | `apps/planning/tests/test_models.py` |
| ☐ | `team/models.py` | Signal `ContractHistory` — `weekly_hours` mis à jour sur `Collaborator` | `apps/team/tests/test_models.py` |
| ☐ | `team/models.py` | Signal `ContractHistory` — ancien contrat fermé (end_date = start_date - 1j) | `apps/team/tests/test_models.py` |
| ☐ | `resources/models.py` | `Category` — unicité `(pharmacy, nom)` → IntegrityError si doublon | `apps/resources/tests/test_models.py` |
| ☐ | `planning/models.py` | `TimeAdjustment` — `duration_minutes <= 0` → violation CheckConstraint | `apps/planning/tests/test_models.py` |
| 🆕 | `team/models.py` | **`Collaborator.is_active=False`** — ses shifts existants restent accessibles en lecture | `apps/team/tests/test_models.py` |
| 🆕 | `resources/models.py` | **Suppression d'une `Category` avec enfants** — cascade ou protection (comportement documenté) | `apps/resources/tests/test_models.py` |

---

### P2 — Qualité : workflow NC et procédures

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `quality/views.py` | `NonConformityViewSet` — workflow DRAFT→ACTIVE→RESOLVED, transitions invalides bloquées | `apps/quality/tests/test_nc.py` |
| ☐ | `quality/views.py` | `ProcedureViewSet` — hiérarchie parent/child, un enfant ne peut pas être son propre parent | `apps/quality/tests/test_procedures.py` |
| ☐ | `quality/views.py` | `ProcedureNotificationViewSet` — `is_read=False` count correct, pas de fuite inter-pharmacie | `apps/quality/tests/test_notifications.py` |
| ☐ | `quality/views.py` | `ProcedureVersion` — création version sur PATCH du contenu | `apps/quality/tests/test_procedures.py` |
| 🆕 | `quality/views.py` | **NC RESOLVED → DRAFT** — transition retour arrière bloquée | `apps/quality/tests/test_nc.py` |
| 🆕 | `quality/views.py` | **Suppression NC en statut ACTIVE** — autorisée uniquement par admin | `apps/quality/tests/test_nc.py` |
| 🆕 | `quality/views.py` | **`ProcedureVersion` — rollback** vers version précédente | `apps/quality/tests/test_procedures.py` |

---

### P2 — SMS et crédit

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `core/views_sms.py` | Envoi SMS — débit crédits correct, `SMSLog` créé | `apps/core/tests/test_sms.py` |
| ☐ | `core/views_sms.py` | Envoi SMS — crédits insuffisants → 402 | `apps/core/tests/test_sms.py` |
| ☐ | `core/views_sms.py` | Webhook OVH — statut `DELIVERED` mis à jour sur `SMSLog` | `apps/core/tests/test_sms.py` |
| ☐ | `core/views_sms.py` | `preview/` — message GSM-7 : comptage correct ; message Unicode : comptage différent | `apps/core/tests/test_sms.py` |
| 🆕 | `core/views_sms.py` | **Envoi simultané** — race condition crédits → `select_for_update` évite double débit | `apps/core/tests/test_sms.py` |
| 🆕 | `core/views_sms.py` | **Destinataire numéro invalide** (pas format E.164) → 400/422 avant consommation crédits | `apps/core/tests/test_sms.py` |
| 🆕 | `core/views_sms.py` | **Message vide** → 400 avant consommation de crédits | `apps/core/tests/test_sms.py` |

---

### P3 — Isolation inter-pharmacie (ownership)

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | Tous les GET | Pharmacie A ne voit pas les données de la Pharmacie B | `tests/test_isolation.py` |
| ☐ | `planning/views.py` | Shift d'une autre pharmacie — PATCH → 404 | `tests/test_isolation.py` |
| ☐ | `quality/views.py` | Procédure d'une autre pharmacie — GET → 404 | `tests/test_isolation.py` |
| ☐ | `messaging/views.py` | Message d'une autre pharmacie — GET → 404 | `tests/test_isolation.py` |
| 🆕 | Tous les POST | **Création avec `pharmacy` d'une autre pharmacie dans le body** → ignoré, pharmacy du token utilisée | `tests/test_isolation.py` |
| 🆕 | `team/views.py` | **Filtre `?collaborator_id=<id_autre_pharmacie>`** → résultat vide, pas 403 ni données étrangères | `tests/test_isolation.py` |
| 🆕 | `planning/views.py` | **DELETE shift d'une autre pharmacie** → 404 | `tests/test_isolation.py` |

---

### 🆕 P2 — Performance & SQL

> Vérifient que l'ORM ne génère pas de requêtes N+1 et que les index critiques sont utilisés.

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| 🆕 | `calculator.py` | **N+1 sur `pharmacy_week_summary`** — 20 collaborateurs → nombre de requêtes SQL constant (`assertNumQueries`) | `apps/planning/tests/test_performance.py` |
| 🆕 | `paye_analytics.py` | **N+1 sur calcul paye** — 10 collaborateurs → nombre de requêtes SQL borné | `apps/planning/tests/test_performance.py` |
| 🆕 | `planning/views.py` | **`TemplateApplyView` bulk** — 50 shifts créés en une seule transaction | `apps/planning/tests/test_performance.py` |

---

### 🆕 P2 — Tests d'intégration flux complets

> Scénarios métier de bout en bout, plus proches de la réalité d'usage.

| # | Scénario | Étapes | Fichier test |
|---|----------|--------|--------------|
| 🆕 | **Flux planning complet** | Créer template → Appliquer semaine → Publier → Vérifier récap hebdo calculé | `tests/integration/test_flux_planning.py` |
| 🆕 | **Flux absence + paye** | Poser absence (CP) → Approuver → Calculer paye → Vérifier jours ouvrés déduits | `tests/integration/test_flux_absences.py` |
| 🆕 | **Flux onboarding pharmacie** | Créer compte → Créer collaborateur → Premier login collaborateur PIN | `tests/integration/test_flux_onboarding.py` |
| 🆕 | **Flux NC qualité** | Déclarer NC → Passer ACTIVE → Résoudre → Vérifier notification générée | `tests/integration/test_flux_qualite.py` |
| 🆕 | **Flux SMS** | Vérifier crédits → Envoyer SMS → Vérifier débit → Simuler webhook DELIVERED | `tests/integration/test_flux_sms.py` |

---

## FRONTEND — Angular 18

### P1 — Services critiques

| # | Fichier cible | Cas à tester | Fichier test |
|---|--------------|--------------|--------------|
| ☐ | `planning.service.ts` | `bulkReplaceTemplateShifts()` — succès : 201 retourné | `planning.service.spec.ts` |
| ☐ | `planning.service.ts` | `pollGenerateTemplate()` — status `pending` puis `done` | `planning.service.spec.ts` |
| ☐ | `planning.service.ts` | `updateShift()` — 409 Conflict géré et propagé | `planning.service.spec.ts` |
| ☐ | `auth.service.ts` | Token expiré → refresh automatique, échec → logout | `auth.service.spec.ts` |
| ☐ | `auth.service.ts` | `active_collaborator_id` lu/écrit dans localStorage | `auth.service.spec.ts` |
| 🆕 | `planning.service.ts` | **`pollGenerateTemplate()` — timeout** (>10 tentatives) → erreur propagée | `planning.service.spec.ts` |
| 🆕 | `planning.service.ts` | **`pollGenerateTemplate()` — status `error`** retourné par l'API → erreur propagée | `planning.service.spec.ts` |
| 🆕 | `auth.service.ts` | **Refresh token invalide** → logout + redirect `/login` avec `returnUrl` | `auth.service.spec.ts` |
| 🆕 | `auth.service.ts` | **Requête parallèle pendant refresh** — une seule requête refresh envoyée (pas de double refresh) | `auth.service.spec.ts` |

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
| ☐ | `auth.guard.ts` | Non connecté → redirige vers `/login` avec `returnUrl` | `auth.guard.spec.ts` |
| ☐ | `onboarding.guard.ts` | Onboarding non complété → redirige vers `/onboarding` | `onboarding.guard.spec.ts` |
| ☐ | `planning-manager.guard.ts` | Collaborateur sans `can_manage_planning` → accès refusé | `planning-manager.guard.spec.ts` |
| 🆕 | `auth.guard.ts` | **`returnUrl` préservé** après login réussi → redirect vers URL initiale | `auth.guard.spec.ts` |
| 🆕 | `planning-manager.guard.ts` | **Collaborateur avec `can_manage_planning=True`** → accès accordé | `planning-manager.guard.spec.ts` |

---

## Commandes pour lancer les tests

```bash
# Backend — tous les tests
cd backend_lien_officinal
.venv/bin/python manage.py test

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
