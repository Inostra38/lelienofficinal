from django.db import migrations


DESCRIPTIONS = {
    "Grossistes-répartiteurs": (
        "Plateformes et portails des grossistes-répartiteurs pharmaceutiques permettant de passer des commandes "
        "de médicaments, de suivre les livraisons, de consulter les disponibilités et de gérer les retours. "
        "Concerne les acteurs de la distribution intermédiaire entre les laboratoires et les officines. "
        "Exemples typiques : Alliance Healthcare, OCP Pharmalia, CERP RRM, Phoenix Pharma, McKesson."
    ),
    "Laboratoires directs": (
        "Accès aux espaces professionnels des laboratoires pharmaceutiques pour passer des commandes directes, "
        "consulter les catalogues produits, suivre les promotions en cours, télécharger des documents techniques "
        "ou réglementaires, et accéder aux informations produits. "
        "Exemples typiques : Boiron, Sanofi, Servier, Ipsen, Biogaran, Teva, Mylan."
    ),
    "Dépositaires": (
        "Plateformes des dépositaires pharmaceutiques, intermédiaires spécialisés dans la distribution de certaines "
        "gammes ou marques, notamment pour les médicaments à prescription restreinte, les produits sous température "
        "dirigée ou les médicaments de spécialité. "
        "Exemples typiques : Meddispar, Eurapharm, Pharma Lab."
    ),
    "Back-office": (
        "Outils de gestion administrative et opérationnelle interne à l'officine : suivi des paiements fournisseurs, "
        "tableaux de bord de performance, gestion des remises et ristournes, reporting commercial, suivi des "
        "avoirs, outils de pilotage de l'activité officinale. "
        "Exemples typiques : NIFTY, FAKS, Highco, Pharmavie, PHR."
    ),
    "Comptabilité & fiscalité": (
        "Logiciels et services dédiés à la comptabilité, à la facturation et à la gestion fiscale de l'officine : "
        "comptabilité analytique, déclarations TVA, liasse fiscale, bilan comptable, gestion des immobilisations, "
        "cabinet comptable en ligne spécialisé pharmacie. "
        "Exemples typiques : Cegid, Sage, ACD, FIDUCIAL, experts-comptables spécialisés officine."
    ),
    "Ressources humaines": (
        "Outils de gestion du personnel de l'officine : planning des équipes, gestion des congés, fiches de paie, "
        "déclarations sociales, convention collective de la pharmacie d'officine, recrutement, formation interne "
        "et entretiens annuels. "
        "Exemples typiques : Octime, PayFit, Silae, URSSAF, syndicats patronaux."
    ),
    "Qualité & conformité": (
        "Ressources liées aux démarches qualité en officine, à la traçabilité réglementaire, aux bonnes pratiques "
        "de dispensation (BPD), à la gestion documentaire qualité, aux audits internes, aux procédures de rappel "
        "de lots, et au respect des normes ANSM. Inclut la gestion des alertes sanitaires. "
        "Exemples typiques : Démarche Qualité Officine, Contrôle des Températures, PHARMODEL."
    ),
    "Gestion des stocks": (
        "Outils de gestion, d'optimisation et de surveillance des stocks médicamenteux et non médicamenteux : "
        "suivi des ruptures d'approvisionnement, alertes de péremption, gestion des rotations, outils de "
        "déstockage, inventaires, commandes automatiques et signalement des ruptures aux autorités. "
        "Exemples typiques : Vigirupture, MediDestock, ANSM ruptures, Pharstock."
    ),
    "Outils patients": (
        "Services numériques orientés vers la relation et le suivi des patients : gestion des rendez-vous, "
        "programmes de fidélité, suivi des ordonnances, historique médicamenteux, alertes de renouvellement, "
        "dossier pharmaceutique (DP), entretiens pharmaceutiques. "
        "Exemples typiques : Carte Santégo, Agenda de prise de RDV, Dossier Pharmaceutique, MonPharmacien."
    ),
    "Aide à la dispensation": (
        "Outils d'aide à la décision clinique et thérapeutique au moment de la dispensation : bases de données "
        "médicamenteuses, vérification des interactions, aide en antibiothérapie, fiches de bon usage, "
        "référentiels pour les populations à risque (femmes enceintes, insuffisants rénaux), recommandations "
        "thérapeutiques. "
        "Exemples typiques : AntiobioClic, Le CRAT, Thériaque, Vidal Pro, SPLF Aérosolthérapie."
    ),
    "Aide au comptoir": (
        "Ressources pratiques pour faciliter le conseil et la vente au comptoir : protocoles de triage, guides "
        "de conseil OTC, fiches conseils patients, outils de calcul de posologie, protocoles de coopération, "
        "aide à la substitution générique, et outils d'accompagnement des nouvelles missions officinales. "
        "Exemples typiques : Pharmathèque, Le Comptoir des Pharmacies, protocoles HAS, fiches CESPHARM."
    ),
    "Mutuelles & tiers payant": (
        "Plateformes et services de gestion du tiers payant : télétransmission des feuilles de soins, suivi "
        "des remboursements, gestion des rejets, accès aux répertoires des organismes complémentaires, "
        "gestion des conventions mutuelles, et outils de réconciliation des paiements AMO/AMC. "
        "Exemples typiques : Safe Santé, Santéclair, Itelis, Carte Blanche, ADREA Mutuelle."
    ),
    "Messagerie patient": (
        "Solutions de communication directe avec les patients : envoi de SMS de rappel pour les ordonnances "
        "ou les vaccins, messagerie sécurisée, notifications de disponibilité des commandes, campagnes "
        "d'information santé, et outils de communication post-dispensation. "
        "Exemples typiques : SMS Messenger Google, WhatsApp Business, Doctolib Messages, Apicrypt."
    ),
    "Formation professionnelle": (
        "Plateformes et organismes de formation continue pour les pharmaciens, préparateurs et étudiants : "
        "DPC (Développement Professionnel Continu), e-learning, webinaires, formations certifiantes, "
        "congrès pharmaceutiques, et outils de gestion du compte personnel de formation (CPF). "
        "Exemples typiques : FIFPL, UNPF, UTIP, Pharma-Formation, associations de DPC agréées."
    ),
    "Veille réglementaire": (
        "Sources d'information juridique et réglementaire pour l'officine : textes de loi, décrets, arrêtés "
        "ministériels, circulaires, mises en garde de l'ANSM, actualités de la convention nationale, "
        "évolutions tarifaires, et informations sur les nouvelles missions confiées aux pharmaciens. "
        "Exemples typiques : ANSM, Légifrance, Journal Officiel, AMELI Pro, Ordre National des Pharmaciens."
    ),
    "Actualités pharmaceutiques": (
        "Sources d'information professionnelle sur l'actualité du secteur pharmaceutique : nouvelles du "
        "marché du médicament, innovations thérapeutiques, politiques de santé, résultats d'études cliniques, "
        "vie syndicale et ordinale, et tendances économiques de l'officine. "
        "Exemples typiques : Le Quotidien du Pharmacien, Impact Pharmacien, Egora, Pharmaradio."
    ),
    "Outils numériques": (
        "Outils digitaux généralistes utiles à la gestion et à la communication de l'officine : création "
        "de supports visuels, assistants intelligents (IA), outils de productivité bureautique, gestion "
        "des réseaux sociaux, création de sites web pour la pharmacie, et solutions de communication interne. "
        "Exemples typiques : Canva, ChatGPT, MedGPT, Google Workspace, Lemur Innovations."
    ),
    "Logiciels & LGO": (
        "Logiciels de gestion officinale (LGO) et solutions intégrées de gestion de la pharmacie : "
        "caisse enregistreuse, gestion des ordonnances, robot de délivrance, interfaces avec les grossistes "
        "et les caisses d'assurance maladie, et modules complémentaires du système d'information officinal. "
        "Exemples typiques : Winpharma, Lgpi, Pharmavitale, PharmaLand, Smart-rx."
    ),
    "Télémédecine & téléservices": (
        "Plateformes et services de santé numérique connectant l'officine aux médecins, aux patients et "
        "au système de santé : prise de rendez-vous médicaux, ordonnances numériques, téléconsultation en "
        "officine, messagerie sécurisée de santé (MSSanté), Mon Espace Santé, et e-prescription. "
        "Exemples typiques : Doctolib Pro, MediMail, Apicrypt, Mon Espace Santé, Lifen."
    ),
    "Préparations magistrales": (
        "Ressources liées à la préparation officinale et magistrale : matières premières, excipients, "
        "logiciels de formulation, bases de données de formules, équipements de préparation, contrôle "
        "qualité des préparations, et réglementation spécifique aux préparations. "
        "Exemples typiques : Cooper, Fagron, SEPPIC, bases de préparations de la Pharmacopée Européenne."
    ),
    "Matériel médical & location": (
        "Services de location et de vente de matériel médical et de maintien à domicile (MAD) : fauteuils "
        "roulants, lits médicalisés, aérosols, déambulateurs, cannes, dispositifs de surveillance, "
        "matériel orthopédique et para-médical. Inclut les prestations de livraison et SAV. "
        "Exemples typiques : Locapharm, Alcura, Pharmat, Air Liquide Santé, VitalAire."
    ),
    "Dermo-cosmétique & parapharmacie": (
        "Ressources dédiées à l'espace de vente parapharmacie et dermo-cosmétique : catalogues produits, "
        "commandes et merchandising des marques cosmétiques, outils de formation au conseil beauté, "
        "PLV et matériel promotionnel, gestion des gammes de compléments alimentaires et des dispositifs "
        "médicaux non remboursés. "
        "Exemples typiques : Pharmacorp, Pharmacorp Hygiestore, PLV Pharmacorp, A-Derma, Avène, La Roche-Posay."
    ),
    "Autre": (
        "Catégorie générique regroupant les ressources qui ne correspondent à aucune des catégories "
        "spécialisées disponibles."
    ),
}


def populate_descriptions(apps, schema_editor):
    WizardCategory = apps.get_model('resources', 'WizardCategory')
    for cat in WizardCategory.objects.all():
        if cat.nom in DESCRIPTIONS:
            cat.description = DESCRIPTIONS[cat.nom]
            cat.save()


def reverse_descriptions(apps, schema_editor):
    WizardCategory = apps.get_model('resources', 'WizardCategory')
    WizardCategory.objects.all().update(description='')


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0007_wizardcategory_description'),
    ]

    operations = [
        migrations.RunPython(populate_descriptions, reverse_descriptions),
    ]
