"""
Management command : peuplement de la base de données pour le développement.

Usage :
    python manage.py seed_dev

Crée 2 pharmacies complètes avec :
  - Collaborateurs
  - Ressources (catégories, cartes, liens)
  - Tâches (personnelles et assignées)
  - Messagerie (conversations et messages)
  - Qualité (tableaux, procédures, versions, non-conformités)

Idempotent : si les pharmacies existent déjà, rien n'est dupliqué.
"""

import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from apps.resources.models import Category, ResourceCard, ResourceItem, PharmacyPreference
from apps.tasks.models import Task
from apps.messaging.models import Conversation, Message
from apps.quality.models import (
    ProcedureGroup, ProcedureCategory, Procedure,
    ProcedureVersion, NonConformity, CorrectiveAction,
)


# ──────────────────────────────────────────────────────────────
# DONNÉES
# ──────────────────────────────────────────────────────────────

PHARMACIES = [
    # ── Pharmacie 1 : Pharmacie du Centre (Montargis) ──────────
    {
        'email': 'centre@test.com',
        'password': 'test1234',
        'nom_officine': 'Pharmacie du Centre',
        'city': 'Montargis',
        'collaborators': [
            {'civility': 'Mme', 'first_name': 'Sophie',  'last_name': 'Martin',  'role': 'Titulaire',   'pin': '1234', 'color': 'green'},
            {'civility': 'M.',  'first_name': 'Marc',    'last_name': 'Dupont',  'role': 'Adjoint',     'pin': '2345', 'color': 'blue'},
            {'civility': 'Mme', 'first_name': 'Julie',   'last_name': 'Bernard', 'role': 'Préparateur', 'pin': '3456', 'color': 'purple'},
            {'civility': 'M.',  'first_name': 'Thomas',  'last_name': 'Leroy',   'role': 'Étudiant',    'pin': '4567', 'color': 'orange'},
        ],
        'categories': [
            {'nom': 'Assurance Maladie',    'ordre': 0},
            {'nom': 'Médicaments & Stocks', 'ordre': 1},
            {'nom': 'Fournisseurs',         'ordre': 2},
            {'nom': 'Outils internes',      'ordre': 3},
        ],
        'cards': [
            {
                'titre': 'Ameli Pro',
                'description_officielle': 'Portail professionnel de l\'Assurance Maladie pour les pharmaciens.',
                'type': 'OFFICIAL',
                'category_nom': 'Assurance Maladie',
                'items': [
                    {'type': 'WEB', 'label': 'Accéder à Ameli Pro', 'url': 'https://www.ameli.fr/pharmacien'},
                    {'type': 'TEL', 'label': 'Hotline Pro AM',       'url': '3608'},
                ],
                'pref': {'is_favorite': True, 'note_courte': 'Indispensable pour les feuilles de soins'},
            },
            {
                'titre': 'Ordre National des Pharmaciens',
                'description_officielle': 'Inscription au tableau et ressources réglementaires.',
                'type': 'OFFICIAL',
                'category_nom': 'Assurance Maladie',
                'items': [
                    {'type': 'WEB', 'label': 'Site de l\'Ordre', 'url': 'https://www.ordre.pharmacien.fr'},
                ],
                'pref': {'is_favorite': False, 'note_courte': ''},
            },
            {
                'titre': 'DOSSIER STOCK — Antibiotiques',
                'description_officielle': '',
                'type': 'PRIVATE',
                'category_nom': 'Médicaments & Stocks',
                'items': [
                    {'type': 'WEB', 'label': 'Suivi ruptures ANSM', 'url': 'https://ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments'},
                ],
                'pref': {
                    'is_favorite': True,
                    'note_courte': 'Vérifier hebdo',
                    'note_longue': 'Amoxicilline 1g : commander chez CERP si Phoenix en rupture.\nAugmentin sirop : alternative Biogaran dispo.',
                },
            },
            {
                'titre': 'CERP Rouen',
                'description_officielle': '',
                'type': 'PRIVATE',
                'category_nom': 'Fournisseurs',
                'items': [
                    {'type': 'WEB', 'label': 'Commande en ligne', 'url': 'https://www.cerp.fr'},
                    {'type': 'TEL', 'label': 'Commercial CERP',   'url': '02 35 XX XX XX'},
                ],
                'pref': {'is_favorite': True, 'note_courte': 'Livraison J+1 si commande avant 16h'},
            },
            {
                'titre': 'Logiciel LGPI',
                'description_officielle': '',
                'type': 'PRIVATE',
                'category_nom': 'Outils internes',
                'items': [
                    {'type': 'TEL', 'label': 'Support LGPI',   'url': '0 810 600 810'},
                    {'type': 'WEB', 'label': 'Base de connaissance', 'url': 'https://www.lgpi.fr/support'},
                ],
                'pref': {'is_favorite': False, 'note_courte': 'N° client : PH-4521'},
            },
        ],
        'tasks': [
            {
                'title': 'Commander Doliprane 1000mg boîte 8',
                'description': 'Rupture signalée par CERP. Commander chez Phoenix en secours.',
                'priority': 'HIGH',
                'status': 'TODO',
                'type': 'PERSONAL',
                'created_by_idx': 1,   # Marc
                'assigned_to_idx': None,
                'due_date': (datetime.date.today() + datetime.timedelta(days=1)),
            },
            {
                'title': 'Vérifier les dates de péremption — rayon homéopathie',
                'description': 'Contrôle trimestriel. Retirer les produits périmés avant fin du mois.',
                'priority': 'MEDIUM',
                'status': 'IN_PROGRESS',
                'type': 'ASSIGNED',
                'created_by_idx': 0,   # Sophie
                'assigned_to_idx': 2,  # Julie
                'due_date': (datetime.date.today() + datetime.timedelta(days=7)),
            },
            {
                'title': 'Mettre à jour l\'affichage prix — rayon parapharmacie',
                'description': '',
                'priority': 'LOW',
                'status': 'TODO',
                'type': 'PERSONAL',
                'created_by_idx': 2,   # Julie
                'assigned_to_idx': None,
                'due_date': None,
            },
            {
                'title': 'Former Thomas à la substitution génériques',
                'description': 'Session pratique de 30 min sur le logiciel LGPI.',
                'priority': 'MEDIUM',
                'status': 'TODO',
                'type': 'ASSIGNED',
                'created_by_idx': 0,   # Sophie
                'assigned_to_idx': 1,  # Marc
                'due_date': (datetime.date.today() + datetime.timedelta(days=14)),
            },
            {
                'title': 'Renouveler contrat maintenance frigo',
                'description': 'Contrat Mediline expire le 31/03. Appeler le commercial.',
                'priority': 'HIGH',
                'status': 'DONE',
                'type': 'PERSONAL',
                'created_by_idx': 0,   # Sophie
                'assigned_to_idx': None,
                'due_date': (datetime.date.today() - datetime.timedelta(days=3)),
            },
        ],
        'conversations': [
            {
                'subject': 'Planning de la semaine',
                'creator_idx': 0,
                'participant_indices': [0, 1, 2, 3],
                'messages': [
                    (0, 'Bonjour à tous ! Le planning de la semaine est disponible sur le drive.'),
                    (1, 'Merci Sophie. Je suis disponible samedi si besoin de renfort.'),
                    (2, 'Pareil, je peux décaler ma pause jeudi sans problème.'),
                    (0, 'Super, je valide ça. Thomas, tu es OK pour ouvrir mardi matin ?'),
                    (3, 'Oui pas de souci, j\'arrive à 8h45 !'),
                ],
            },
            {
                'subject': 'Rupture de stock Doliprane',
                'creator_idx': 1,
                'participant_indices': [0, 1, 2],
                'messages': [
                    (1, 'Attention : rupture Doliprane 500mg boîte 16. CERP annonce J+5 minimum.'),
                    (0, 'Merci Marc. On oriente vers Dafalgan en attendant.'),
                    (2, 'J\'ai encore 3 boîtes en réserve si urgence patient.'),
                    (1, 'Bien noté Julie. Je mets une alerte sur le logiciel.'),
                ],
            },
            {
                'subject': 'Nouvelle réglementation — Arrêté du 12 mars',
                'creator_idx': 0,
                'participant_indices': [0, 1],
                'messages': [
                    (0, 'Marc, as-tu lu la circulaire sur les nouvelles obligations d\'affichage ?'),
                    (1, 'Oui, je l\'ai parcourue. On doit mettre à jour 3 panneaux avant fin avril.'),
                    (0, 'J\'ai commandé les nouveaux visuels chez notre imprimeur. Arrivée jeudi.'),
                ],
            },
        ],
        'quality': {
            'groups': [
                {
                    'name': 'Hygiène & Sécurité',
                    'description': 'Procédures liées à la sécurité du personnel et de la patientèle',
                    'color': '#D32F2F',
                    'order': 0,
                    'creator_idx': 0,
                },
                {
                    'name': 'Gestion des Stocks',
                    'description': 'Réception, stockage, péremptions et retours fournisseurs',
                    'color': '#1565C0',
                    'order': 1,
                    'creator_idx': 1,
                },
                {
                    'name': 'Accueil & Dispensation',
                    'description': 'Procédures de conseil et de délivrance au comptoir',
                    'color': '#2E7D32',
                    'order': 2,
                    'creator_idx': 0,
                },
            ],
            'proc_categories': [
                {'name': 'Obligatoire',    'color': '#C62828'},
                {'name': 'Recommandé',     'color': '#1565C0'},
                {'name': 'Qualité ISO',    'color': '#2E7D32'},
                {'name': 'Interne',        'color': '#6A1B9A'},
            ],
            'procedures': [
                {
                    'title': 'Lavage des mains — protocole standard',
                    'reference': 'HYG-001',
                    'status': 'active',
                    'group_idx': 0,
                    'cat_names': ['Obligatoire', 'Qualité ISO'],
                    'pilot_indices': [1],
                    'creator_idx': 0,
                    'content': '## Objectif\nGarantir l\'hygiène des mains de tout le personnel avant et après contact avec les patients.\n\n## Fréquence\n- Avant chaque conseil au comptoir\n- Après manipulation de médicaments\n- En sortant des espaces de stockage\n\n## Procédure\n1. Mouiller les mains à l\'eau tiède\n2. Appliquer le savon pendant **30 secondes minimum**\n3. Rincer abondamment\n4. Sécher avec essuie-mains à usage unique\n5. Utiliser le gel hydroalcoolique si point d\'eau indisponible\n\n## Produits autorisés\n- Savon liquide ANIOS\n- SHA Stérilium (gel)\n\n## Points de contrôle\n- [ ] Distributeurs de SHA rechargés\n- [ ] Essuie-mains disponibles\n- [ ] Affichage protocole visible',
                    'version': 2,
                    'history': [
                        {'v': 1, 'summary': 'Version initiale', 'creator_idx': 0},
                        {'v': 2, 'summary': 'Ajout SHA Stérilium + checklist de contrôle', 'creator_idx': 1},
                    ],
                    'next_review': (datetime.date.today() + datetime.timedelta(days=180)),
                },
                {
                    'title': 'Réception et contrôle des commandes',
                    'reference': 'STK-001',
                    'status': 'active',
                    'group_idx': 1,
                    'cat_names': ['Obligatoire'],
                    'pilot_indices': [1, 2],
                    'creator_idx': 1,
                    'content': '## Objectif\nAssurer la conformité et la traçabilité de chaque réception fournisseur.\n\n## Étapes\n1. **Contrôle quantitatif** : Compter les boîtes livrées vs bon de livraison\n2. **Contrôle qualitatif** : Vérifier intégrité des emballages\n3. **Contrôle sérialisation** : Scanner les codes DataMatrix (Décret 2019-111)\n4. **Rangement** : Appliquer la règle FEFO (First Expired, First Out)\n5. **Saisie informatique** : Enregistrer dans LGPI sous 2h\n\n## En cas d\'anomalie\n- Refuser le colis endommagé\n- Contacter le commercial fournisseur\n- Remplir le formulaire de litige (dossier Fournisseurs)',
                    'version': 1,
                    'history': [
                        {'v': 1, 'summary': 'Création suite audit ARS', 'creator_idx': 1},
                    ],
                    'next_review': (datetime.date.today() + datetime.timedelta(days=365)),
                },
                {
                    'title': 'Dispensation des stupéfiants',
                    'reference': 'DIS-002',
                    'status': 'active',
                    'group_idx': 2,
                    'cat_names': ['Obligatoire', 'Qualité ISO'],
                    'pilot_indices': [0],
                    'creator_idx': 0,
                    'content': '## Cadre réglementaire\nArrêté du 31 mars 1999 relatif à la prescription et à la dispensation des médicaments appartenant aux listes I et II et des médicaments stupéfiants.\n\n## Vérifications obligatoires\n1. Ordonnance sécurisée (carnet à souche)\n2. Identité du patient (pièce d\'identité si > 600€ ou 1ère délivrance)\n3. Date de validité (28 jours pour les stupéfiants)\n4. Concordance posologie/durée\n5. Fractionnement si durée > 7 jours mentionnée\n\n## Enregistrement\n- Registre informatique LGPI (automatique à la dispensation)\n- Conservation ordonnance 3 ans\n\n## Accès au coffre\n- Coffre fermé à clé en permanence\n- Clé dans le tiroir verrouillé du bureau titulaire',
                    'version': 3,
                    'history': [
                        {'v': 1, 'summary': 'Version initiale', 'creator_idx': 0},
                        {'v': 2, 'summary': 'Mise à jour suite arrêté 2022', 'creator_idx': 0},
                        {'v': 3, 'summary': 'Ajout procédure coffre + accès', 'creator_idx': 1},
                    ],
                    'next_review': (datetime.date.today() + datetime.timedelta(days=90)),
                },
                {
                    'title': 'Gestion des péremptions',
                    'reference': 'STK-002',
                    'status': 'draft',
                    'group_idx': 1,
                    'cat_names': ['Recommandé'],
                    'pilot_indices': [2],
                    'creator_idx': 2,
                    'content': '## Fréquence des contrôles\n- Mensuel : produits à rotation lente\n- Trimestriel : ensemble du stock\n\n## Procédure\n1. Scanner les rayons avec la douchette LGPI (mode péremption)\n2. Retirer les produits périmant dans < 3 mois\n3. Proposer en promotion si vente possible\n4. Retourner au grossiste si accord (avoir fournisseur)\n5. Détruire selon procédure CYCLAMED\n\n## Formulaires\n- BDC retour grossiste (dossier Fournisseurs/Retours)\n- Bordereau CYCLAMED (à conserver 5 ans)',
                    'version': 1,
                    'history': [
                        {'v': 1, 'summary': 'Brouillon initial', 'creator_idx': 2},
                    ],
                    'next_review': None,
                },
            ],
            'nonconformities': [
                {
                    'title': 'Température frigo vaccins hors plage (>8°C)',
                    'description': 'Alarme déclenchée le 18/03 à 6h22. Température relevée : 9,4°C. Durée estimée : 2h. Les vaccins concernés ont été isolés.',
                    'severity': 'major',
                    'status': 'in_progress',
                    'reported_by_idx': 1,
                    'assigned_to_idx': 0,
                    'due_date': (datetime.date.today() + datetime.timedelta(days=5)),
                    'corrective_actions': [
                        {
                            'description': 'Contacter le fabricant des vaccins pour statuer sur leur utilisation.',
                            'responsible_idx': 0,
                            'due_date': (datetime.date.today() + datetime.timedelta(days=2)),
                        },
                        {
                            'description': 'Faire vérifier le système d\'alarme par le technicien Mediline.',
                            'responsible_idx': 1,
                            'due_date': (datetime.date.today() + datetime.timedelta(days=5)),
                        },
                    ],
                },
                {
                    'title': 'Erreur de dispensation — patient a reçu un mauvais dosage',
                    'description': 'Patient M. Durand a reçu Metformine 850mg au lieu de 500mg. Détecté lors du rappel téléphonique. Patient prévenu, aucun effet indésirable signalé.',
                    'severity': 'critical',
                    'status': 'open',
                    'reported_by_idx': 2,
                    'assigned_to_idx': 0,
                    'due_date': (datetime.date.today() + datetime.timedelta(days=3)),
                    'corrective_actions': [
                        {
                            'description': 'Rappeler le patient et vérifier son état de santé. Informer son médecin traitant.',
                            'responsible_idx': 0,
                            'due_date': datetime.date.today(),
                        },
                        {
                            'description': 'Analyser la cause : confusion de boîte ou erreur de saisie LGPI.',
                            'responsible_idx': 1,
                            'due_date': (datetime.date.today() + datetime.timedelta(days=2)),
                        },
                    ],
                },
            ],
        },
    },

    # ── Pharmacie 2 : Pharmacie de la Gare (Orléans) ───────────
    {
        'email': 'gare@test.com',
        'password': 'test1234',
        'nom_officine': 'Pharmacie de la Gare',
        'city': 'Orléans',
        'collaborators': [
            {'civility': 'M.',  'first_name': 'Pierre', 'last_name': 'Leclerc',  'role': 'Titulaire',   'pin': '1111', 'color': 'teal'},
            {'civility': 'Mme', 'first_name': 'Emma',   'last_name': 'Rousseau', 'role': 'Adjoint',     'pin': '2222', 'color': 'pink'},
            {'civility': 'M.',  'first_name': 'Lucas',  'last_name': 'Petit',    'role': 'Préparateur', 'pin': '3333', 'color': 'amber'},
        ],
        'categories': [
            {'nom': 'Santé & Remboursements', 'ordre': 0},
            {'nom': 'Fournisseurs',           'ordre': 1},
            {'nom': 'Ressources internes',    'ordre': 2},
        ],
        'cards': [
            {
                'titre': 'Ameli Pro',
                'description_officielle': 'Portail professionnel de l\'Assurance Maladie.',
                'type': 'OFFICIAL',
                'category_nom': 'Santé & Remboursements',
                'items': [
                    {'type': 'WEB', 'label': 'Ameli Pro', 'url': 'https://www.ameli.fr/pharmacien'},
                ],
                'pref': {'is_favorite': True, 'note_courte': ''},
            },
            {
                'titre': 'Phoenix Pharma',
                'description_officielle': '',
                'type': 'PRIVATE',
                'category_nom': 'Fournisseurs',
                'items': [
                    {'type': 'WEB', 'label': 'Commande Phoenix', 'url': 'https://www.phoenix-pharma.fr'},
                    {'type': 'TEL', 'label': 'SAV Phoenix',      'url': '0 810 05 45 00'},
                ],
                'pref': {'is_favorite': True, 'note_courte': 'Dépôt à 15h30 chaque jour'},
            },
            {
                'titre': 'Protocoles internes',
                'description_officielle': '',
                'type': 'PRIVATE',
                'category_nom': 'Ressources internes',
                'items': [],
                'pref': {
                    'is_favorite': False,
                    'note_courte': 'Voir dossier qualité',
                    'note_longue': 'Tous les protocoles sont dans le classeur rouge sous le comptoir principal.',
                },
            },
        ],
        'tasks': [
            {
                'title': 'Inventaire mensuel — rayon OTC',
                'description': 'Comptage physique et mise à jour LGPI.',
                'priority': 'HIGH',
                'status': 'TODO',
                'type': 'ASSIGNED',
                'created_by_idx': 0,
                'assigned_to_idx': 2,
                'due_date': (datetime.date.today() + datetime.timedelta(days=3)),
            },
            {
                'title': 'Renouveler inscription DPC',
                'description': 'Formation obligatoire 2 jours avant fin d\'année.',
                'priority': 'MEDIUM',
                'status': 'TODO',
                'type': 'PERSONAL',
                'created_by_idx': 1,
                'assigned_to_idx': None,
                'due_date': (datetime.date.today() + datetime.timedelta(days=30)),
            },
            {
                'title': 'Nettoyer et recalibrer balance de préparation',
                'description': '',
                'priority': 'LOW',
                'status': 'DONE',
                'type': 'PERSONAL',
                'created_by_idx': 2,
                'assigned_to_idx': None,
                'due_date': None,
            },
        ],
        'conversations': [
            {
                'subject': 'Réunion d\'équipe lundi',
                'creator_idx': 0,
                'participant_indices': [0, 1, 2],
                'messages': [
                    (0, 'Réunion lundi 9h en salle de pause. Ordre du jour : formations DPC et nouveau planning été.'),
                    (1, 'Noté, je serai là. J\'apporte les CR de la dernière réunion.'),
                    (2, 'Présent aussi ! J\'ai une question sur les congés de juillet.'),
                    (0, 'On en parlera lundi Lucas, j\'ai déjà les demandes sous les yeux.'),
                ],
            },
            {
                'subject': 'Point stock insulines',
                'creator_idx': 1,
                'participant_indices': [0, 1],
                'messages': [
                    (1, 'Pierre, notre stock de Lantus SoloSTAR est à 4 stylos seulement.'),
                    (0, 'Je commande aujourd\'hui. Tu peux contacter les patients sous Lantus pour les prévenir ?'),
                    (1, 'Oui, je le fais ce matin. On a 3 patients en attente de renouvellement.'),
                ],
            },
        ],
        'quality': {
            'groups': [
                {
                    'name': 'Réglementation',
                    'description': 'Procédures réglementaires obligatoires',
                    'color': '#C62828',
                    'order': 0,
                    'creator_idx': 0,
                },
                {
                    'name': 'Qualité opérationnelle',
                    'description': 'Procédures du quotidien',
                    'color': '#2E7D32',
                    'order': 1,
                    'creator_idx': 1,
                },
            ],
            'proc_categories': [
                {'name': 'Obligatoire', 'color': '#C62828'},
                {'name': 'Interne',     'color': '#6A1B9A'},
            ],
            'procedures': [
                {
                    'title': 'Ouverture et fermeture de l\'officine',
                    'reference': 'OP-001',
                    'status': 'active',
                    'group_idx': 1,
                    'cat_names': ['Interne'],
                    'pilot_indices': [0],
                    'creator_idx': 0,
                    'content': '## Ouverture (8h30)\n1. Désactiver alarme (code : voir cahier sécurité)\n2. Allumer les postes informatiques\n3. Vérifier températures frigo (consigner dans le cahier)\n4. Préparer le fond de caisse\n5. Déverrouiller la porte principale\n\n## Fermeture (19h30)\n1. Encaisser le dernier client\n2. Éditer le rapport de caisse LGPI\n3. Fermer et verrouiller le coffre\n4. Éteindre tous les postes\n5. Vérifier fenêtres et portes\n6. Activer l\'alarme',
                    'version': 1,
                    'history': [
                        {'v': 1, 'summary': 'Création', 'creator_idx': 0},
                    ],
                    'next_review': None,
                },
                {
                    'title': 'Traitement des retours patients',
                    'reference': 'OP-002',
                    'status': 'draft',
                    'group_idx': 1,
                    'cat_names': ['Interne'],
                    'pilot_indices': [1],
                    'creator_idx': 1,
                    'content': '## Médicaments non ouverts\n- Accepter si emballage intact et non périmé\n- Orienter vers collecte CYCLAMED\n\n## Médicaments détériorés ou périmés\n- Refuser le remboursement\n- Proposer CYCLAMED\n\n## Dispositifs médicaux\n- Retour fournisseur uniquement si défaut avéré\n- Contacter SAV dans les 48h',
                    'version': 1,
                    'history': [
                        {'v': 1, 'summary': 'Brouillon', 'creator_idx': 1},
                    ],
                    'next_review': None,
                },
            ],
            'nonconformities': [
                {
                    'title': 'Ordonnance non datée délivrée',
                    'description': 'Un patient s\'est présenté avec une ordonnance sans date. La dispensation a été effectuée par erreur.',
                    'severity': 'minor',
                    'status': 'closed',
                    'reported_by_idx': 2,
                    'assigned_to_idx': 0,
                    'due_date': (datetime.date.today() - datetime.timedelta(days=10)),
                    'corrective_actions': [
                        {
                            'description': 'Rappel à l\'équipe : vérification systématique de la date sur chaque ordonnance.',
                            'responsible_idx': 0,
                            'due_date': (datetime.date.today() - datetime.timedelta(days=8)),
                        },
                    ],
                },
            ],
        },
    },
]


# ──────────────────────────────────────────────────────────────
# COMMANDE
# ──────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Peuple la base de données avec des données de développement réalistes'

    def handle(self, *args, **options):
        with transaction.atomic():
            for pharm_data in PHARMACIES:
                self._seed_pharmacy(pharm_data)

        self.stdout.write(self.style.SUCCESS('\n✅ Base peuplée avec succès !\n'))
        self.stdout.write('Comptes disponibles :')
        for p in PHARMACIES:
            self.stdout.write(f"  📧 {p['email']}  🔑 {p['password']}  ({p['nom_officine']})")
        self.stdout.write('')

    # ── Pharmacie ──────────────────────────────────────────────

    def _seed_pharmacy(self, data):
        pharmacy, created = Pharmacy.objects.get_or_create(
            email=data['email'],
            defaults={
                'nom_officine': data['nom_officine'],
                'city': data['city'],
                'onboarding_completed': True,
                'is_active': True,
            }
        )
        if created:
            pharmacy.set_password(data['password'])
            pharmacy.save()
            self.stdout.write(f"\n  ➕ {pharmacy.nom_officine}")
        else:
            self.stdout.write(f"\n  ⏭️  {pharmacy.nom_officine} (existante)")

        collabs = self._seed_collaborators(pharmacy, data['collaborators'])
        self._seed_resources(pharmacy, data['categories'], data['cards'])
        self._seed_tasks(pharmacy, collabs, data['tasks'])
        self._seed_messaging(pharmacy, collabs, data['conversations'])
        self._seed_quality(pharmacy, collabs, data['quality'])

    # ── Collaborateurs ─────────────────────────────────────────

    def _seed_collaborators(self, pharmacy, collabs_data):
        collabs = []
        for c in collabs_data:
            obj, created = Collaborator.objects.get_or_create(
                pharmacy=pharmacy,
                first_name=c['first_name'],
                last_name=c['last_name'],
                defaults={'civility': c['civility'], 'role': c['role'], 'color': c['color'], 'is_active': True}
            )
            if created:
                obj.set_pin(c['pin'])
                obj.save()
                self.stdout.write(f"    👤 {obj}  PIN: {c['pin']}")
            collabs.append(obj)
        return collabs

    # ── Ressources ─────────────────────────────────────────────

    def _seed_resources(self, pharmacy, cats_data, cards_data):
        categories = {}
        for cat_data in cats_data:
            cat, _ = Category.objects.get_or_create(
                owner_pharmacy=pharmacy,
                nom=cat_data['nom'],
                defaults={'ordre': cat_data['ordre']}
            )
            categories[cat_data['nom']] = cat

        for i, card_data in enumerate(cards_data):
            cat = categories.get(card_data['category_nom'])
            card, created = ResourceCard.objects.get_or_create(
                titre=card_data['titre'],
                owner_pharmacy=pharmacy,
                defaults={
                    'description_officielle': card_data['description_officielle'],
                    'type': card_data['type'],
                    'category': cat,
                    'ordre': i,
                }
            )
            if created:
                for j, item_data in enumerate(card_data['items']):
                    ResourceItem.objects.create(
                        card=card,
                        type=item_data['type'],
                        label=item_data['label'],
                        url=item_data.get('url', ''),
                        owner=pharmacy,
                        ordre=j,
                    )
                pref_data = card_data.get('pref', {})
                PharmacyPreference.objects.get_or_create(
                    pharmacy=pharmacy,
                    card=card,
                    defaults={
                        'assigned_category': cat,
                        'is_favorite': pref_data.get('is_favorite', False),
                        'note_courte': pref_data.get('note_courte', ''),
                        'note_longue': pref_data.get('note_longue', ''),
                    }
                )
                self.stdout.write(f"    🗂️  {card.titre}")

    # ── Tâches ─────────────────────────────────────────────────

    def _seed_tasks(self, pharmacy, collabs, tasks_data):
        for i, t in enumerate(tasks_data):
            Task.objects.get_or_create(
                pharmacy=pharmacy,
                title=t['title'],
                defaults={
                    'description': t['description'],
                    'priority': t['priority'],
                    'status': t['status'],
                    'type': t['type'],
                    'created_by': collabs[t['created_by_idx']],
                    'assigned_to': collabs[t['assigned_to_idx']] if t['assigned_to_idx'] is not None else None,
                    'due_date': t['due_date'],
                    'order': i,
                }
            )
        self.stdout.write(f"    ✅ {len(tasks_data)} tâches")

    # ── Messagerie ─────────────────────────────────────────────

    def _seed_messaging(self, pharmacy, collabs, convs_data):
        for conv_data in convs_data:
            creator = collabs[conv_data['creator_idx']]
            participants = [collabs[i] for i in conv_data['participant_indices']]
            conv, created = Conversation.objects.get_or_create(
                pharmacy=pharmacy,
                subject=conv_data['subject'],
                defaults={'created_by': creator}
            )
            if created:
                conv.participants.set(participants)
                for sender_idx, content in conv_data['messages']:
                    Message.objects.create(conversation=conv, sender=collabs[sender_idx], content=content)
                self.stdout.write(f"    💬 {conv.subject}")

    # ── Qualité ────────────────────────────────────────────────

    def _seed_quality(self, pharmacy, collabs, quality_data):
        groups = []
        for g in quality_data['groups']:
            group, _ = ProcedureGroup.objects.get_or_create(
                pharmacy=pharmacy,
                name=g['name'],
                defaults={
                    'description': g['description'],
                    'color': g['color'],
                    'order': g['order'],
                    'created_by': collabs[g['creator_idx']],
                }
            )
            groups.append(group)

        proc_cats = {}
        for pc in quality_data['proc_categories']:
            cat, _ = ProcedureCategory.objects.get_or_create(
                pharmacy=pharmacy,
                name=pc['name'],
                defaults={'color': pc['color']}
            )
            proc_cats[pc['name']] = cat

        for i, p in enumerate(quality_data['procedures']):
            proc, created = Procedure.objects.get_or_create(
                pharmacy=pharmacy,
                reference=p['reference'],
                defaults={
                    'title': p['title'],
                    'status': p['status'],
                    'group': groups[p['group_idx']],
                    'content': p['content'],
                    'version': p['version'],
                    'position': i,
                    'created_by': collabs[p['creator_idx']],
                    'next_review_date': p['next_review'],
                }
            )
            if created:
                proc.categories.set([proc_cats[n] for n in p['cat_names'] if n in proc_cats])
                proc.pilots.set([collabs[idx] for idx in p['pilot_indices']])
                for h in p['history']:
                    ProcedureVersion.objects.get_or_create(
                        procedure=proc,
                        version_number=h['v'],
                        defaults={
                            'content': proc.content,
                            'change_summary': h['summary'],
                            'created_by': collabs[h['creator_idx']],
                        }
                    )
                self.stdout.write(f"    📋 [{proc.reference}] {proc.title}")

        for nc_data in quality_data['nonconformities']:
            nc, created = NonConformity.objects.get_or_create(
                pharmacy=pharmacy,
                title=nc_data['title'],
                defaults={
                    'description': nc_data['description'],
                    'severity': nc_data['severity'],
                    'status': nc_data['status'],
                    'reported_by': collabs[nc_data['reported_by_idx']],
                    'assigned_to': collabs[nc_data['assigned_to_idx']],
                    'due_date': nc_data['due_date'],
                }
            )
            if created:
                for ca in nc_data['corrective_actions']:
                    CorrectiveAction.objects.create(
                        nonconformity=nc,
                        description=ca['description'],
                        responsible=collabs[ca['responsible_idx']],
                        due_date=ca['due_date'],
                    )
                self.stdout.write(f"    ⚠️  NC : {nc.title[:50]}")
