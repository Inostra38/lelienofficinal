# 07 — Modèle de données

> **Compétence DWWM couverte ici :** **CP5** — Créer une base de données (modélisation
> entité-association, contraintes d'intégrité, index).

## 7.1 Principes transverses

### Multi-tenant par le modèle utilisateur

`AUTH_USER_MODEL = core.Pharmacy` : **l'utilisateur authentifié *est* la pharmacie**.
Il n'y a pas de table « tenant » séparée. Presque tous les modèles portent une clé
étrangère `pharmacy` (ou `owner_pharmacy`) vers `Pharmacy`, et chaque `get_queryset`
de l'API filtre dessus. Des tests de non-régression verrouillent l'isolation
(`tests/test_isolation.py`, `apps/core/tests/test_audit_idor_20260709.py`).

### Overlay de préférences (`PharmacyPreference`)

Les cartes de ressources `OFFICIAL` et `PARTNER` sont **partagées** entre toutes les
pharmacies (catalogue commun maintenu par l'admin ou les laboratoires). Chaque
officine pose par-dessus une **surcouche** `PharmacyPreference`
(`unique_together (pharmacy, card)`) : favori, masquage, catégorie assignée, note
courte, note longue, ordre d'affichage. Les vues créent cette ligne à la volée via
`get_or_create` lors de la première personnalisation.

### Secrets et données sensibles

| Donnée | Traitement |
|---|---|
| Mot de passe pharmacie | `AbstractBaseUser` — haché (PBKDF2) |
| PIN collaborateur | `pin_hash` — `make_password` / `check_password`, jamais en clair |
| Contenu des messages, objet de conversation | **`EncryptedTextField`** — chiffré au repos (Fernet) |
| Secret TOTP admin | `Fernet` (clé dédiée `ADMIN_TOTP_KEY`) |
| Numéro de téléphone destinataire SMS | **SHA-256** (`to_hash`) — le numéro en clair n'est jamais stocké |

### Contraintes et index PostgreSQL

`django.contrib.postgres` est activé pour utiliser :
- des **`CheckConstraint`** métier : `sms_credits >= 0`, `end_datetime > start_datetime`
  sur les shifts, `duration > 0` sur les ajustements horaires, énumérations de statut… ;
- des **index partiels** : `Procedure` active, `CollaboratorLoginLog` sur les échecs
  uniquement, unicité de `stripe_payment_intent_id` quand non nul.

## 7.2 Cœur : authentification, équipe, facturation

```mermaid
erDiagram
    PHARMACY ||--o{ COLLABORATOR : "emploie"
    PHARMACY ||--|| SUBSCRIPTION : "possède"
    PHARMACY ||--o{ INVOICE : "reçoit"
    PHARMACY ||--o{ SMSCREDITTRANSACTION : "mouvemente"
    PHARMACY ||--o{ SMSTEMPLATE : "définit"
    PHARMACY ||--o{ SMSLOG : "émet"
    PHARMACY ||--o{ PASSWORDRESETTOKEN : "demande"
    COLLABORATOR ||--o{ CONTRACTHISTORY : "a"
    COLLABORATOR ||--o{ COLLABORATORLOGINLOG : "journalise"
    COLLABORATOR ||--o{ SMSLOG : "envoie"
    SUBSCRIPTION }o--o| PROMOCODE : "via redemption"
    PROMOCODE ||--o{ PROMOREDEMPTION : "consommé par"
    PHARMACY ||--o{ PROMOREDEMPTION : "utilise"

    PHARMACY {
        int id PK
        string email UK
        string nom_officine
        string siret UK
        string region
        int sms_credits "CHECK >= 0"
        bool email_verified
        bool onboarding_completed
        datetime deletion_scheduled_for "RGPD"
        datetime anonymized_at "RGPD"
    }
    COLLABORATOR {
        int id PK
        int pharmacy_id FK
        string first_name
        string last_name
        string role "Titulaire|Adjoint|Préparateur|Étudiant|Apprenti"
        string pin_hash "haché"
        bool can_manage_planning
        bool can_manage_quality
        int pin_fail_count
        datetime pin_locked_until
    }
    CONTRACTHISTORY {
        int id PK
        int collaborator_id FK
        string contract_type "CDI|CDD|APPRENTISSAGE|INTERIM|TNS"
        decimal weekly_hours
        date start_date
        date end_date "null = en cours"
    }
    SUBSCRIPTION {
        int id PK
        int pharmacy_id FK "OneToOne"
        string plan "small|large"
        string status "trialing|active|past_due|suspended|canceled"
        datetime trial_ends_at
        datetime past_due_since "origine grâce 7j"
    }
    INVOICE {
        int id PK
        int pharmacy_id FK
        string invoice_number UK "LLO-AAAA-000001"
        string invoice_type "subscription|sms_pack"
        decimal amount_ht
        decimal amount_ttc
        string pdf_storage_key "Scaleway"
    }
    SMSCREDITTRANSACTION {
        int id PK
        int pharmacy_id FK
        int delta "+ crédit / - débit"
        string reason "purchase|send|refund|closure"
        string stripe_payment_intent_id "unique si non nul"
    }
    SMSLOG {
        int id PK
        int pharmacy_id FK
        string to_hash "SHA-256"
        string status "PENDING|SUCCESS|DELIVERED|FAILED"
        int credits_used
        datetime sent_at "TTL 30 jours"
    }
```

`Subscription.is_access_allowed` est une **propriété calculée** (pas une colonne) :
elle dérive le droit d'accès des dates (`trial_ends_at`, `past_due_since`) et du
statut. Voir [chapitre 09](09-modules-transverses.md).

## 7.3 Ressources (tableau de bord)

```mermaid
erDiagram
    PHARMACY ||--o{ CATEGORY : "possède"
    PHARMACY ||--o{ RESOURCECARD : "crée (PRIVATE)"
    PARTNER ||--o{ RESOURCECARD : "gère (PARTNER)"
    CATEGORY ||--o{ RESOURCECARD : "classe (défaut)"
    RESOURCECARD ||--o{ RESOURCEITEM : "contient"
    RESOURCECARD ||--o{ PHARMACYPREFERENCE : "personnalisée par"
    PHARMACY ||--o{ PHARMACYPREFERENCE : "pose"
    CATEGORY ||--o{ PHARMACYPREFERENCE : "catégorie assignée"

    CATEGORY {
        int id PK
        int owner_pharmacy_id FK
        string nom "unique par pharmacie"
        int ordre
    }
    RESOURCECARD {
        int id PK
        string titre
        string type "OFFICIAL|PARTNER|PRIVATE"
        int owner_pharmacy_id FK "si PRIVATE"
        int owner_partner_id FK "si PARTNER"
        string recommendation_status "PENDING|APPROVED|REJECTED"
    }
    RESOURCEITEM {
        int id PK
        int card_id FK
        string type "WEB|PDF|TEL|MAIL"
        string label
        string url
        file file
    }
    PHARMACYPREFERENCE {
        int id PK
        int pharmacy_id FK
        int card_id FK
        int assigned_category_id FK
        bool is_favorite
        bool is_hidden
        int ordre
        string note_courte "≤ 150 car."
        text note_longue
    }
    WIZARDCATEGORY {
        int id PK
        string nom "global, onboarding"
        int ordre
    }
```

**Recommandation communautaire** : un pharmacien peut proposer une carte/lien privé
à la communauté (`recommended_to_community`, `recommendation_status`,
`target_official_card` = carte officielle de rattachement après validation). L'admin
valide dans le back-office avant promotion en `OFFICIAL`.

## 7.4 Planning

```mermaid
erDiagram
    PHARMACY ||--|| PLANNINGSETTINGS : "configure"
    PHARMACY ||--o{ PHARMACYDAYSTATUS : "ouvre/ferme"
    PHARMACY ||--o{ SHIFT : "planifie"
    PHARMACY ||--o{ OPENINGHOURSVERSION : "versionne"
    OPENINGHOURSVERSION ||--o{ OPENINGHOURS : "détaille"
    COLLABORATOR ||--o{ SHIFT : "affecté à"
    COLLABORATOR ||--o{ ABSENCEREQUEST : "demande"
    COLLABORATOR ||--o{ TIMEADJUSTMENT : "ajuste"
    PHARMACY ||--o{ WEEKTEMPLATE : "modélise"
    WEEKTEMPLATE ||--o{ TEMPLATESHIFT : "compose"
    WEEKTEMPLATE ||--o{ WEEKTEMPLATEAPPLICATION : "appliqué"
    PHARMACY ||--|| CONSTRAINTSET : "borne"
    CONSTRAINTSET ||--o{ CONSTRAINT : "règles"

    SHIFT {
        int id PK
        int pharmacy_id FK
        int collaborator_id FK "SET_NULL + snapshot"
        datetime start_datetime
        datetime end_datetime "CHECK > start"
        bool is_published
        bool is_absent
        string absence_type
        decimal contract_hours_snapshot "figé à la sauvegarde"
    }
    ABSENCEREQUEST {
        int id PK
        int collaborator_id FK
        string type "CP|maladie|RCR|formation|…"
        string status "pending|approved|rejected"
        decimal working_days_count
    }
    WEEKTEMPLATE {
        int id PK
        int pharmacy_id FK
        string letter "A|B|C|D — unique par pharmacie"
    }
    TIMEADJUSTMENT {
        int id PK
        int collaborator_id FK
        string kind "overtime|early_departure"
        decimal duration "CHECK > 0"
    }
    PHARMACYDAYSTATUS {
        int id PK
        date date "unique par pharmacie"
        bool is_closed
        bool on_call_day
        bool on_call_night
    }
```

Le moteur de **paie analytique** (`apps/planning/paye_analytics.py`) agrège shifts,
absences, ajustements et snapshots contractuels pour produire les compteurs d'heures.
Il fait l'objet de 7 modules de tests dédiés (voir
[chapitre 11](11-tests-qualite.md)) et d'une [dette technique documentée](12-limites-dette-roadmap.md).

## 7.5 Qualité

```mermaid
erDiagram
    PHARMACY ||--o{ PROCEDUREGROUP : "organise"
    PHARMACY ||--o{ PROCEDURECATEGORY : "classe"
    PROCEDURECATEGORY ||--o{ PROCEDURE : "contient"
    PROCEDURE ||--o{ PROCEDURE : "parent / enfant"
    PROCEDURE ||--o{ PROCEDUREVERSION : "historise"
    PROCEDURE ||--o{ PROCEDUREATTACHMENT : "pièces jointes"
    PROCEDURE ||--o{ PROCEDUREREADLOG : "lu par (scroll ≥ 90 %)"
    PROCEDURE }o--o{ COLLABORATOR : "pilotes (M2M)"
    PROCEDURE ||--o{ NONCONFORMITY : "concernée par"
    NONCONFORMITY ||--o{ CORRECTIVEACTION : "traitée par"

    PROCEDURE {
        int id PK
        int pharmacy_id FK
        string reference "unique par pharmacie (null-safe)"
        string status "draft|active|archived"
        int version
        int parent_id FK
        date next_review_date
    }
    PROCEDUREVERSION {
        int id PK
        int procedure_id FK
        int version_number "unique par procédure"
        text content_snapshot
    }
    NONCONFORMITY {
        int id PK
        int procedure_id FK "PROTECT"
        string severity "minor|major|critical"
        string status "open|in_progress|closed"
        int reported_by_id FK
        int closed_by_id FK
    }
```

Le module `messaging` (hors schémas ci-dessus pour rester lisible) : `Conversation`
(PK UUID, `subject` chiffré) `1─N` `Message` (PK UUID, `content` chiffré), les deux
reliés aux `Collaborator` participants en M2M.

## 7.6 Migrations

66 migrations, per-app, versionnées dans le dépôt. Deux migrations de données
(`RunPython`). En production, elles sont **appliquées depuis la CI** via le CLI
Scalingo (la phase `release` du Procfile n'étant pas exécutée sur cette application —
voir [chapitre 10](10-deploiement-exploitation.md)).
