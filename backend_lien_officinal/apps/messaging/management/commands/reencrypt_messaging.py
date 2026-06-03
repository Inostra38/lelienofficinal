"""
E5 Phase 1 — Re-chiffrement des champs messagerie après rotation de clé.

Les EncryptedTextField déchiffrent avec n'importe quelle clé de
FIELD_ENCRYPTION_KEY (MultiFernet) mais chiffrent toujours avec la PREMIÈRE.
Après avoir placé une nouvelle clé en tête de FIELD_ENCRYPTION_KEY, lancer
cette commande re-chiffre tout le contenu avec la nouvelle clé ; l'ancienne
peut ensuite être retirée de la configuration.

Usage :
    python manage.py reencrypt_messaging          # applique
    python manage.py reencrypt_messaging --dry-run # compte seulement
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.messaging.models import Conversation, Message


class Command(BaseCommand):
    help = "Re-chiffre les champs messagerie (subject, content) avec la clé courante."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien, affiche seulement le nombre d'enregistrements concernés.",
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help="Taille des lots de traitement (défaut 500).",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        conv_total = Conversation.objects.count()
        msg_total = Message.objects.count()

        if dry_run:
            self.stdout.write(
                f"[dry-run] {conv_total} conversation(s) et {msg_total} message(s) "
                f"seraient re-chiffrés avec la clé courante."
            )
            return

        conv_done = self._reencrypt(Conversation, 'subject', batch_size)
        msg_done = self._reencrypt(Message, 'content', batch_size)

        self.stdout.write(self.style.SUCCESS(
            f"Re-chiffrement terminé : {conv_done} conversation(s), {msg_done} message(s)."
        ))

    def _reencrypt(self, model, field_name, batch_size):
        """
        Re-sauvegarde chaque enregistrement sur le seul champ chiffré : la
        lecture déchiffre (MultiFernet), l'écriture re-chiffre avec la clé
        courante. update_fields limité au champ chiffré → ne touche pas aux
        autres colonnes ni aux timestamps auto_now.
        """
        count = 0
        qs = model.objects.all().only('pk', field_name).order_by('pk')
        for obj in qs.iterator(chunk_size=batch_size):
            with transaction.atomic():
                obj.save(update_fields=[field_name])
            count += 1
            if count % batch_size == 0:
                self.stdout.write(f"  {model.__name__}: {count} traité(s)…")
        return count
