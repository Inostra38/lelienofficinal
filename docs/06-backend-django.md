# 06 — Back-end Django

> **Référentiel — bloc 2, Développement Back End :**
> **`C3.c`** interrogation de la base par l'ORM (§6.4) · **`C4.b`** développement avec
> un langage serveur (§6.2, §6.3) · **`C4.c`** POO et héritage (§6.4) · **`C4.d`**
> architecture MTV/MVC (§6.4) · **`C4.e`** identification de l'utilisateur et
> délimitation de ses droits (§6.4).
> Contribue au **bloc 3** (`C5.b` gestionnaire de dépendances et variables
> d'environnement, §6.1–6.2). Détail en [annexe](annexe-referentiel-competences.md).

## 6.1 Stack

| Élément | Version | Rôle |
|---|---|---|
| Django | **6.0.1** | framework web, ORM, migrations |
| Django REST Framework | **3.16** | API REST (sérialiseurs, vues, permissions) |
| djangorestframework-simplejwt | 5.5 | authentification JWT + *blacklist* |
| Channels + channels-redis + Daphne | 4.3 / 4.3 / 4.2 | WebSocket ASGI |
| Celery | 5.6 | tâches asynchrones (broker Redis) |
| Stripe · WeasyPrint · pyotp · PyJWT · cryptography | — | facturation, PDF, TOTP admin, JWT admin, chiffrement |
| django-encrypted-model-fields | 0.6 | chiffrement de champs au repos |
| django-storages + boto3 | — | Scaleway Object Storage (S3) |
| Python | 3.12 | — |

## 6.2 Configuration — un seul fichier, piloté par l'environnement

`backend_lien_officinal/settings.py` est **unique** (pas de `settings/base.py` +
`prod.py`). La distinction dev/prod se fait sur la variable `DEBUG`, et toute la
configuration sensible vient de `os.environ` (chargé via `python-dotenv`).

`settings_test.py` est un mince dérivé : `from .settings import *` puis SQLite
en mémoire, cache factice (désactive le *throttling*), redirection HTTPS neutralisée.

### Garde-fous au démarrage (fail-safe)

L'application **refuse de démarrer** si un secret est faible ou manquant
(`settings.py:38-73`) :

```python
DEBUG = os.environ.get('DEBUG', 'False') == 'True'   # F2 : désactivé par défaut

SECRET_KEY = os.environ.get('SECRET_KEY')
# C3 : interdire le démarrage avec une clé faible/par défaut, quel que soit DEBUG.
if not SECRET_KEY or SECRET_KEY.startswith('django-insecure'):
    raise Exception("SECRET_KEY manquante ou non sécurisée…")

# E1 : secrets admin dédiés, INDÉPENDANTS de SECRET_KEY
ADMIN_JWT_SECRET = os.environ.get('ADMIN_JWT_SECRET')
ADMIN_TOTP_KEY   = os.environ.get('ADMIN_TOTP_KEY')
if not DEBUG and (not ADMIN_JWT_SECRET or not ADMIN_TOTP_KEY):
    raise Exception("ADMIN_JWT_SECRET et ADMIN_TOTP_KEY doivent être définis…")

FIELD_ENCRYPTION_KEY = [k.strip() for k in os.environ.get('FIELD_ENCRYPTION_KEY', '').split(',') if k.strip()]
if not FIELD_ENCRYPTION_KEY:
    raise Exception("FIELD_ENCRYPTION_KEY manquante…")
```

En production (`not DEBUG`), sont activés : `SECURE_SSL_REDIRECT`, HSTS 1 an +
*preload* + sous-domaines, `SECURE_PROXY_SSL_HEADER`, cookies de session et CSRF
`Secure`.

### Sélection de la base de données (`settings.py:181`)

Trois priorités : `DATABASE_URL` (Scalingo) → variables `DB_*` séparées → **SQLite**
(développement local sans dépendance).

## 6.3 Découpage en applications

Le dossier `apps/` est ajouté au `sys.path`, ce qui permet des imports courts
(`apps.core`). Dix applications métier :

| App | Responsabilité |
|---|---|
| `core` | modèle **`Pharmacy`** (= `AUTH_USER_MODEL`), authentification, onboarding, e-mail, SMS, suppression RGPD |
| `team` | **`Collaborator`** (sans compte, connexion par PIN), historique de contrats, journal de connexion |
| `resources` | catalogue de liens : `Category`, `ResourceCard`, `ResourceItem`, **`PharmacyPreference`** (surcouche par officine) |
| `partners` | laboratoires / grossistes, encarts publicitaires d'inactivité |
| `messaging` | `Conversation` / `Message` — **contenu chiffré au repos** (données de santé) |
| `tasks` | tâches personnelles / assignées, commentaires |
| `planning` | 16 migrations : shifts, absences, gardes, modèles de semaine, ajustements horaires, moteur de paie |
| `quality` | procédures hiérarchiques versionnées, non-conformités, actions correctives, pilotes |
| `admin_panel` | back-office SaaS interne : **`AdminUser`** distinct, TOTP, *IP whitelist*, journal d'audit |
| `billing` | abonnements Stripe, factures, transactions de crédits SMS, codes promo |

## 6.4 API REST

### Style mixte, assumé

- **ViewSets + routeurs** (`DefaultRouter`) là où le CRUD est régulier : `core`
  (pharmacie, templates SMS, logs SMS), `resources` (catégories, cartes, items),
  `quality` (8 *viewsets*), `team` (`CollaboratorViewSet` avec de nombreuses
  `@action` : `login`, `verify-pin`, `reorder`, `unlock-pin`…).
- **`APIView` / vues génériques** là où la logique est spécifique : `planning`
  (~40 vues), `messaging`, `tasks`, `billing`, `admin_panel`.

### Routage

`backend_lien_officinal/urls.py` : `/api/health/`, `/media/<path>` (protégé par JWT),
inclusions des apps sous `/api/`, `/api/quality/`, `/api/admin/`, `/api/billing/`,
plus `/api/token/` + `/api/token/refresh/`. L'admin Django n'est monté qu'en `DEBUG` ;
en production, une route attrape-tout sert le SPA Angular.

### Exemple représentatif — tenant + accès payant

`apps/core/views_sms.py` :

```python
class SMSTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = SMSTemplateSerializer
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get_queryset(self):
        return SMSTemplate.objects.filter(pharmacy=self.request.user).order_by('title')

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user)
```

Deux principes systématiques :
1. **Isolation multi-tenant** — chaque `get_queryset` filtre sur
   `pharmacy=self.request.user` (l'utilisateur authentifié *est* la pharmacie).
2. **`perform_create` force le propriétaire** — le client ne peut pas injecter un
   `pharmacy` arbitraire dans le corps de la requête.

### Permissions

- Défaut global : `IsAuthenticated` (`REST_FRAMEWORK` dans `settings.py`).
  `SessionAuthentication` est **volontairement exclu** pour éviter les conflits CSRF
  avec le cookie admin.
- **`HasPaidAccess`** (`apps/billing/permissions.py`) — lève `PaymentRequired`
  (**HTTP 402**) ; présente sur ~70 vues des modules payants. Voir
  [chapitre 09](09-modules-transverses.md).
- **`apps/quality/permissions.py`** — `IsPharmacyTitulaire`, `CanManageProcedures`,
  `CanPublishProcedures`, `CanCloseNonConformities`, `CanEditProcedure` (niveau
  objet : vérifie que le collaborateur est pilote de la procédure). Un jeton « accès
  direct pharmacie » (sans `collaborator_id`) est traité comme Titulaire implicite.

### Throttling (`settings.py:341`)

```python
'DEFAULT_THROTTLE_RATES': {
    'user': '1000/day',
    'login': '10/min',          'register': '5/hour',
    'messaging': '30/minute',
    'sms_send': '200/hour',     'sms_send_collaborator': '50/hour',
    'admin_login': '5/hour',    'admin_totp': '10/hour',
    'promo_validate': '10/min',
}
```

Complété par des classes de *throttle* dédiées : `PinVerifyThrottle`
(10 tentatives / 5 min, `parse_rate` custom), `ForgotPasswordThrottle`,
`SMSCollaboratorThrottle` (clé = `token['collaborator_id']`), etc.

## 6.5 Tâches asynchrones — Celery

`backend_lien_officinal/celery.py` : `autodiscover_tasks()`, broker et backend de
résultats = Redis, sérialisation JSON, fuseau `Europe/Paris`.

| Tâche | Fichier | Rôle |
|---|---|---|
| `send_verification_email_task`, `send_password_reset_task`, `send_email_change_task` | `apps/core/tasks.py` | e-mails Mailgun, 3 tentatives |
| `send_sms_task` | `apps/core/tasks.py` | envoi via SMS Partner, 2 tentatives ; en cas d'échec définitif, **remboursement des crédits** + `SmsCreditTransaction` dans un bloc atomique (audit `C21`) |
| `execute_scheduled_deletions` | `apps/core/tasks.py` | **balayage RGPD** : anonymise les comptes dont la date de suppression est atteinte |
| `cleanup_old_sms_logs` | `apps/core/tasks.py` | purge des `SMSLog` de plus de 30 jours |
| `schedule_suspension`, `check_plan_upgrades`, `credit_sms_balance`, `generate_subscription_invoice`, `generate_sms_receipt` | `apps/billing/tasks.py` | cycle de vie abonnement, re-tiering nocturne, PDF WeasyPrint |
| `generate_template_task` | `apps/planning/tasks.py` | génération IA d'un modèle de planning (streaming Anthropic), résultat mis en cache, *polling* côté front |

### Ordonnanceur (`CELERY_BEAT_SCHEDULE`)

Trois tâches nocturnes : purge des logs SMS (02:00), vérification des paliers
d'abonnement (02:00), **exécution des suppressions RGPD programmées (02:30)**.

L'ordonnanceur (**beat**) tourne **dans le worker** (`Procfile`, option `--beat`),
pas dans un conteneur dédié — ce qui impose de garder le worker à **un seul
conteneur** (chaque conteneur embarquant son propre beat, en scaler deux
dupliquerait chaque tâche planifiée). Détail dans
[chapitre 10](10-deploiement-exploitation.md).

## 6.6 Temps réel — Channels

`asgi.py` route les *urlpatterns* WebSocket de `messaging`, `tasks`, `quality` et
`core` (statut SMS), le tout encapsulé dans `AllowedHostsOriginValidator`
(anti-*Cross-Site WebSocket Hijacking*, audit `S22`).

`apps/messaging/middleware.py` — `JWTAuthMiddleware` : le jeton arrive en
**sous-protocole** `['bearer', '<jwt>']`, est décodé avec `SECRET_KEY`, doit porter
`auth_type == 'collaborator'`, et charge le `Collaborator` correspondant.

`apps/messaging/consumers.py` — `ConversationConsumer` : codes de fermeture
`4001` (pas de collaborateur), **`4402`** (abonnement requis — écho du 402 REST),
`4003` (non participant) ; limiteur de débit intégré 30 messages / 60 s ;
enregistrement du `Message` (chiffré) puis diffusion au groupe.

## 6.7 Base de données et migrations

- **PostgreSQL** en production, **SQLite** en dev/tests. `django.contrib.postgres`
  activé (index partiels, `CheckConstraint`).
- **66 migrations** au total (planning 16, core 12, team 8, billing 7, quality 6…),
  dont deux migrations de données (`RunPython`) : *backfill* des abonnements existants,
  crédit de 20 SMS aux comptes antérieurs.
- Commandes de *seed* pour le développement : `seed_dev`, `seed_sms_logs`,
  `seed_test_pharmacy`, `seed_planning`, `create_test_collaborators`.
- Commandes d'exploitation : `reencrypt_messaging` (rotation de clé de chiffrement),
  `create_admin`, `inspect_subscription`, `trigger_test_invoice`.

Le modèle de données complet est décrit au [chapitre 07](07-modele-de-donnees.md).
