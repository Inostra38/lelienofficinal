"""
Management command : peuplement de l'historique SMS pour le développement.

Usage :
    python manage.py seed_sms_logs
    python manage.py seed_sms_logs --pharmacy-id 1  # pharmacie spécifique
    python manage.py seed_sms_logs --clear           # vide les logs avant de seeder

Crée 20 entrées SMSLog réalistes sur les 30 derniers jours avec statuts variés.
Idempotent si --clear n'est pas passé (ne duplique pas si des logs existent déjà).
"""

import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Pharmacy, SMSLog, SMSTemplate
from apps.core.services import SMSPartnerService
from apps.team.models import Collaborator


DESTINATAIRES = [
    ('M.', 'Martin Bernard'),
    ('Mme', 'Sophie Lefebvre'),
    ('M.', 'Pierre Dubois'),
    ('Mme', 'Marie Fontaine'),
    ('M.', 'Jacques Moreau'),
    ('Mme', 'Isabelle Renard'),
    ('M.', 'François Laurent'),
    ('Mme', 'Nathalie Simon'),
    ('M.', 'Alain Petit'),
    ('Mme', 'Christine Rousseau'),
    ('M.', 'Éric Girard'),
    ('Mme', 'Valérie Mercier'),
]

MOTIFS = [
    'Commande médicaments chroniques',
    'Renouvellement ordonnance',
    'Résultat test rapide',
    'Disponibilité produit',
    'Suivi traitement',
    'Rappel rendez-vous vaccin',
    'Livraison à domicile',
    '',
]

PHONES = [
    '0612345678', '0698765432', '0623456789',
    '0687654321', '0634567890', '0676543210',
]


class Command(BaseCommand):
    help = "Peuple l'historique SMS avec des données de développement réalistes."

    def add_arguments(self, parser):
        parser.add_argument('--pharmacy-id', type=int, help='ID de la pharmacie cible')
        parser.add_argument('--clear', action='store_true', help='Vide les logs existants avant de seeder')
        parser.add_argument('--count', type=int, default=20, help='Nombre de logs à créer (défaut : 20)')

    def handle(self, *args, **options):
        pharmacy_id = options.get('pharmacy_id')

        if pharmacy_id:
            try:
                pharmacy = Pharmacy.objects.get(pk=pharmacy_id)
            except Pharmacy.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Pharmacie #{pharmacy_id} introuvable.'))
                return
        else:
            pharmacy = Pharmacy.objects.first()
            if not pharmacy:
                self.stderr.write(self.style.ERROR('Aucune pharmacie en base. Lance seed_dev d\'abord.'))
                return

        if options['clear']:
            deleted, _ = SMSLog.objects.filter(pharmacy=pharmacy).delete()
            self.stdout.write(self.style.WARNING(f'{deleted} logs supprimés.'))

        templates = list(SMSTemplate.objects.filter(pharmacy=pharmacy))
        collaborators = list(Collaborator.objects.filter(pharmacy=pharmacy, is_active=True))
        if not collaborators:
            self.stderr.write(self.style.WARNING('Aucun collaborateur actif — sent_by sera NULL.'))
        count = options['count']
        now = timezone.now()

        # Répartition des statuts : 60% DELIVERED, 20% SUCCESS, 10% FAILED, 10% PENDING
        statuts_pool = (
            [SMSLog.Status.DELIVERED] * 12
            + [SMSLog.Status.SUCCESS] * 4
            + [SMSLog.Status.FAILED] * 2
            + [SMSLog.Status.PENDING] * 2
        )

        created = 0
        for i in range(count):
            civilite, nom = random.choice(DESTINATAIRES)
            phone = random.choice(PHONES)
            to_hash = SMSPartnerService.hash_phone(phone)
            motif = random.choice(MOTIFS)
            status = random.choice(statuts_pool)
            template = random.choice(templates) if templates and random.random() > 0.3 else None
            credits_used = random.choice([1, 1, 1, 2])
            days_ago = random.uniform(0, 29)
            sent_at = now - timedelta(days=days_ago)

            ovh_id = ''
            error_msg = ''
            if status in (SMSLog.Status.SUCCESS, SMSLog.Status.DELIVERED):
                ovh_id = f'MOCK-{uuid.uuid4().hex[:8].upper()}'
            elif status == SMSLog.Status.FAILED:
                credits_used = 0
                error_msg = random.choice([
                    'Numéro invalide ou hors zone',
                    'Numéro non joignable',
                    'Timeout connexion SMS Partner API',
                ])

            sent_by = random.choice(collaborators) if collaborators else None

            log = SMSLog.objects.create(
                pharmacy=pharmacy,
                template=template,
                sent_by=sent_by,
                to_hash=to_hash,
                recipient_civilite=civilite,
                recipient_name=nom,
                motif=motif,
                status=status,
                provider_message_id=ovh_id,
                credits_used=credits_used,
                error_message=error_msg,
            )
            # sent_at est auto_now_add → rétrodater via update
            SMSLog.objects.filter(pk=log.pk).update(sent_at=sent_at)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{created} logs SMS créés pour « {pharmacy.nom_officine} » '
                f'(pharmacie #{pharmacy.pk}).'
            )
        )
