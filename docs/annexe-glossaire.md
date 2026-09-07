# Annexe A2 — Glossaire

## Métier — officine

| Terme | Définition |
|---|---|
| **Officine** | Pharmacie de ville (par opposition à la pharmacie à usage intérieur d'un hôpital). Marché cible du Lien Officinal. |
| **Titulaire** | Pharmacien(ne) propriétaire de l'officine. Seul habilité à en être juridiquement responsable ; dans l'application, il détient tous les droits (rôle inaltérable). |
| **Adjoint** | Pharmacien salarié diplômé, peut remplacer le titulaire au comptoir. |
| **Préparateur** | Préparateur en pharmacie (BP), délivre sous contrôle du pharmacien. |
| **Garde** | Période d'ouverture obligatoire hors horaires normaux (nuit, dimanche, jours fériés) assurée à tour de rôle par les officines d'un secteur. L'application distingue garde **de jour** et garde **de nuit**. |
| **CFA** | Centre de formation d'apprentis. Un apprenti est absent de l'officine ses jours de CFA — le planning en tient compte. |
| **TNS** | Travailleur non salarié (ex. titulaire, cogérant). Régime social et calcul d'heures spécifiques dans le moteur de paie. |
| **NC** | Non-conformité : écart constaté par rapport à une procédure qualité. Gravité mineure / majeure / critique, suivie par des actions correctives jusqu'à clôture. |
| **Pilote (qualité)** | Collaborateur responsable d'une procédure : sa rédaction, ses mises à jour, sa revue périodique. |
| **Démarche qualité** | Obligation réglementaire des officines (arrêté du 28 novembre 2016) : procédures écrites, traçabilité, gestion des NC. Le module Qualité outille cette obligation. |
| **HDS** | Hébergement de Données de Santé. Certification obligatoire (art. L1111-8 CSP) pour héberger des données de santé à caractère personnel pour le compte de tiers. |
| **Grossiste-répartiteur** | Intermédiaire logistique entre laboratoires et officines (ex. OCP, CERP). Cible fréquente des raccourcis du tableau de bord. |

## Technique

| Terme | Définition |
|---|---|
| **SPA** | *Single-Page Application* — application web dont la navigation se fait côté client sans rechargement de page. |
| **JWT** | *JSON Web Token* — jeton signé transportant l'identité et les droits, permettant une authentification sans session serveur. |
| **Jeton de *refresh*** | Jeton à durée de vie longue servant à obtenir de nouveaux jetons d'accès courts. Ici stocké en **cookie HttpOnly** (invisible au JavaScript). |
| **TOTP** | *Time-based One-Time Password* — code à usage unique dérivé d'un secret partagé et de l'heure (Google Authenticator, etc.). Second facteur du back-office admin. |
| **Multi-tenant** | Architecture où une même instance applicative sert plusieurs clients (« tenants ») avec cloisonnement des données. Ici, chaque **pharmacie** est un tenant. |
| **IDOR** | *Insecure Direct Object Reference* — faille permettant d'accéder aux données d'un autre tenant en manipulant un identifiant. Contrée par le filtrage systématique `pharmacy=request.user` et des tests dédiés. |
| **ORM** | *Object-Relational Mapping* — couche traduisant les objets Python en requêtes SQL (ici, l'ORM de Django). |
| **Migration** | Script versionné décrivant une évolution du schéma de base de données. |
| **ASGI** | *Asynchronous Server Gateway Interface* — interface serveur Python asynchrone, nécessaire pour les WebSockets. Serveur utilisé : **Daphne**. |
| **WebSocket** | Canal bidirectionnel persistant entre navigateur et serveur, pour le temps réel (messagerie, notifications). |
| **Celery** | File de tâches distribuée Python : exécute en arrière-plan les traitements longs (e-mails, SMS, PDF, purges). |
| **Broker** | Intermédiaire de messages entre l'application et les workers Celery. Ici : **Redis**. |
| **beat** | Ordonnanceur de Celery : déclenche les tâches périodiques (purges nocturnes). |
| **PaaS** | *Platform as a Service* — hébergement qui gère l'infrastructure (ici **Scalingo**), l'application se déployant par `git push`. |
| **buildpack** | Script de construction d'une application sur un PaaS (installation des dépendances, compilation). |
| **WhiteNoise** | Bibliothèque servant les fichiers statiques directement depuis l'application Django, sans serveur web dédié. |
| **CSP** | *Content Security Policy* — en-tête HTTP restreignant les sources de scripts/styles/images, défense en profondeur contre le XSS. |
| **CSWSH** | *Cross-Site WebSocket Hijacking* — détournement de WebSocket depuis un site tiers. Contré par `AllowedHostsOriginValidator`. |
| **Fernet / MultiFernet** | Schéma de chiffrement symétrique authentifié (bibliothèque `cryptography`). MultiFernet gère plusieurs clés pour la rotation. |
| **GSM-7 / Unicode (SMS)** | Encodages d'un SMS : GSM-7 (160 caractères/segment) pour l'alphabet latin de base, Unicode (70 caractères/segment) dès qu'un caractère sort de ce jeu (emoji, certains accents). |
| **402 Payment Required** | Code HTTP utilisé ici pour signaler qu'un module nécessite un abonnement actif (sans déconnecter l'utilisateur). |
| **RGAA** | Référentiel général d'amélioration de l'accessibilité — norme française d'accessibilité numérique, citée par le critère `C1.c`. |
| **Tronc commun / bloc optionnel** | Le titre **Développeur Web** s'obtient en validant le bloc 1 (Front End) + le bloc 2 (Back End), **un** bloc optionnel — ici le **bloc 3, Framework** — et une période de stage. |
