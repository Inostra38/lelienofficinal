from django.core.management.base import BaseCommand
from apps.resources.models import ResourceCard, ResourceItem


RESOURCES = [
    # ─── GROSSISTES ────────────────────────────────────────────────────────────
    {
        'titre': 'CERP RRM',
        'description': '2 livraisons par jour (matin tôt et 14h) du lundi au samedi',
        'items': [{'type': 'WEB', 'label': 'Espace client CERP RRM', 'url': 'https://monespaceclient.cerp-rrm.com/login'}],
    },
    {
        'titre': 'OCP Pharmalia',
        'description': '1 livraison matin (9h) du mardi au samedi',
        'items': [{'type': 'WEB', 'label': 'OCP Pharmalia pharmacien', 'url': 'https://www.ocp-pharmalia.fr/ocp-pharmacien/'}],
    },
    {
        'titre': 'Alliance Healthcare',
        'description': '1 livraison (9h) du mardi au samedi',
        'items': [{'type': 'WEB', 'label': 'Alliance Healthcare', 'url': 'https://my.alliance-healthcare.fr/'}],
    },
    {
        'titre': 'Locapharm – Alcura',
        'description': 'Livraison lendemain Chronopost / La Poste',
        'items': [{'type': 'WEB', 'label': 'Locapharm santé', 'url': 'https://www.locapharm-sante.fr/connexion.php'}],
    },
    {
        'titre': 'Pharmacorp – Hygiestore',
        'description': 'Produits avec frais de port',
        'items': [{'type': 'WEB', 'label': 'Hygiestore', 'url': 'https://hygiestore.fr/'}],
    },
    {
        'titre': 'Boiron',
        'description': 'Livraison via CERP le lendemain après-midi',
        'items': [{'type': 'WEB', 'label': 'Boiron Pro', 'url': 'https://keycloak.boiron-pro.fr/'}],
    },
    {
        'titre': 'Pharmat',
        'description': 'Livraison CERP lendemain après-midi',
        'items': [{'type': 'WEB', 'label': 'MyPharmat', 'url': 'https://mypharmat.com/'}],
    },

    # ─── SERVICES PATIENTS ─────────────────────────────────────────────────────
    {
        'titre': 'Lemur Innovations',
        'description': 'Entretiens pharmaceutiques, questionnaires courts, TROD',
        'items': [{'type': 'WEB', 'label': 'Lemur – Espace pharmacie', 'url': 'https://app.lemur-innov.fr/pharmacy/home'}],
    },
    {
        'titre': 'Doctolib Pro',
        'description': 'Accès ordonnances et messagerie patients',
        'items': [{'type': 'WEB', 'label': 'Doctolib Pro', 'url': 'https://pro.doctolib.fr/patient_messaging'}],
    },
    {
        'titre': 'Safe Santé',
        'description': 'Téléconsultation et accès ordonnances',
        'items': [{'type': 'WEB', 'label': 'Safe Santé Pharma', 'url': 'https://pharma.safesante.fr/login'}],
    },
    {
        'titre': 'Carte Santégo',
        'description': 'Module de gestion des cartes de fidélité',
        'items': [{'type': 'WEB', 'label': 'Santégo partenaire', 'url': 'https://www.santego.com/partner/5616843'}],
    },
    {
        'titre': 'Agenda – Prise de RDV',
        'description': 'Accès aux calendriers de la pharmacie',
        'items': [{'type': 'WEB', 'label': 'Google Calendar', 'url': 'https://calendar.google.com/calendar/'}],
    },

    # ─── COMMUNICATION ─────────────────────────────────────────────────────────
    {
        'titre': 'WhatsApp Business',
        'description': 'Communication avec les patients',
        'items': [{'type': 'WEB', 'label': 'WhatsApp Web', 'url': 'https://web.whatsapp.com'}],
    },
    {
        'titre': 'SMS Messenger Google',
        'description': 'Envoi de SMS gratuit depuis le téléphone de la pharmacie',
        'items': [{'type': 'WEB', 'label': 'Google Messages Web', 'url': 'https://messages.google.com/web/welcome'}],
    },

    # ─── BACK-OFFICE ───────────────────────────────────────────────────────────
    {
        'titre': 'FAKS',
        'description': 'Descriptions et données produits',
        'items': [{'type': 'WEB', 'label': 'FAKS Web', 'url': 'https://web.faks.co/login/phone_number'}],
    },
    {
        'titre': 'OPEAZ',
        'description': 'Descriptions et données produits',
        'items': [{'type': 'WEB', 'label': 'OPEAZ App', 'url': 'https://app.opeaz.fr/'}],
    },
    {
        'titre': 'Pharmacorp',
        'description': 'Site du groupement Pharmacorp',
        'items': [{'type': 'WEB', 'label': 'Pharmacorp Web', 'url': 'https://pharmacorp.fr/PHARMACORP_WEB/FR/'}],
    },
    {
        'titre': 'PLV Pharmacorp',
        'description': "Logiciel de confection d'affiches promotionnelles",
        'items': [{'type': 'WEB', 'label': 'Pharmacorp PLV', 'url': 'https://app.pharmacorp-plv.fr/'}],
    },
    {
        'titre': 'Le Comptoir des Pharmacies',
        'description': 'Picking approvisionnement et déstockage',
        'items': [{'type': 'WEB', 'label': 'Le Comptoir des Pharmacies', 'url': 'https://www.lecomptoirdespharmacies.fr/connexion'}],
    },
    {
        'titre': 'MediDestock',
        'description': 'Déstockage de médicaments',
        'items': [{'type': 'WEB', 'label': 'MediDestock', 'url': 'https://medi-destock.com/'}],
    },
    {
        'titre': 'Canva',
        'description': "Création d'affiches et supports promotionnels",
        'items': [{'type': 'WEB', 'label': 'Canva', 'url': 'https://www.canva.com/design/'}],
    },
    {
        'titre': 'Démarche Qualité Officine',
        'description': 'Aide à la certification qualité officine',
        'items': [{'type': 'WEB', 'label': 'DQO', 'url': 'https://www.demarchequaliteofficine.fr/'}],
    },
    {
        'titre': 'Contrôle Températures',
        'description': 'Enregistrement des courbes de température',
        'items': [{'type': 'WEB', 'label': 'Saveris Net', 'url': 'https://www.saveris.net/MeasuringPts/'}],
    },
    {
        'titre': 'NIFTY',
        'description': 'Coupons de réduction smartphone',
        'items': [{'type': 'WEB', 'label': 'NIFTY Highco', 'url': 'https://nifty.highco.com/'}],
    },
    {
        'titre': 'Highco – Suivi paiements',
        'description': 'Suivi des paiements NIFTY',
        'items': [{'type': 'WEB', 'label': 'Highco Suivi', 'url': 'https://distribution.highco-data.fr/suivipaiement.aspx'}],
    },

    # ─── RESSOURCES MÉDICALES ──────────────────────────────────────────────────
    {
        'titre': 'Meddispar',
        'description': "Médicaments à dispensation particulière à l'officine",
        'items': [{'type': 'WEB', 'label': 'Meddispar', 'url': 'https://www.meddispar.fr/'}],
    },
    {
        'titre': 'Le CRAT',
        'description': 'Médicaments et vaccins : grossesse & allaitement',
        'items': [{'type': 'WEB', 'label': 'Le CRAT', 'url': 'https://www.lecrat.fr/medicament-grossesse/'}],
    },
    {
        'titre': 'AntiobioClic',
        'description': "Outil d'aide à la décision en antibiothérapie",
        'items': [{'type': 'WEB', 'label': 'AntiobioClic', 'url': 'https://antibioclic.com/'}],
    },
    {
        'titre': 'Vigirupture',
        'description': 'Recherche de médicaments disponibles chez les confrères',
        'items': [{'type': 'WEB', 'label': 'Vigirupture', 'url': 'https://www.vigirupture.fr/login/'}],
    },
    {
        'titre': 'SPLF – Aérosolthérapie',
        'description': "Vidéos sur l'observance des médicaments inhalés",
        'items': [{'type': 'WEB', 'label': 'SPLF Vidéos Zéphir', 'url': 'https://splf.fr/videos-zephir/'}],
    },

    # ─── VACCINATIONS & VOYAGES ────────────────────────────────────────────────
    {
        'titre': 'Vaccination Info Service',
        'description': 'Calendrier vaccinal et recommandations vaccinales',
        'items': [{'type': 'WEB', 'label': 'Vaccination Info Service Pro', 'url': 'https://professionnels.vaccination-info-service.fr/'}],
    },
    {
        'titre': 'Institut Pasteur – Voyages',
        'description': 'Zones à risque, vaccinations et recommandations sanitaires',
        'items': [{'type': 'WEB', 'label': 'Pasteur – Préparer son voyage', 'url': 'https://www.pasteur.fr/fr/centre-medical/preparer-son-voyage'}],
    },

    # ─── OUTILS IA ─────────────────────────────────────────────────────────────
    {
        'titre': 'ChatGPT',
        'description': 'Assistant IA généraliste',
        'items': [{'type': 'WEB', 'label': 'ChatGPT', 'url': 'https://chatgpt.com/'}],
    },
    {
        'titre': 'MedGPT',
        'description': "Recherche et synthèse d'articles scientifiques médicaux",
        'items': [{'type': 'WEB', 'label': 'MedGPT', 'url': 'https://medgpt.fr/'}],
    },
]


class Command(BaseCommand):
    help = 'Peuple la base avec les ressources partagées OFFICIAL'

    def handle(self, *args, **kwargs):
        created = 0
        skipped = 0

        for data in RESOURCES:
            card, is_new = ResourceCard.objects.get_or_create(
                titre=data['titre'],
                type='OFFICIAL',
                defaults={'description_officielle': data.get('description', '')}
            )

            if is_new:
                for i, item in enumerate(data['items']):
                    ResourceItem.objects.create(
                        card=card,
                        type=item['type'],
                        label=item['label'],
                        url=item.get('url', ''),
                        ordre=i
                    )
                created += 1
                self.stdout.write(f'  ✓ {card.titre}')
            else:
                skipped += 1
                self.stdout.write(f'  – {card.titre} (déjà existant)')

        self.stdout.write(self.style.SUCCESS(
            f'\n{created} ressource(s) créée(s), {skipped} ignorée(s).'
        ))
