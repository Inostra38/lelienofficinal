import secrets
import string

from django.core.management.base import BaseCommand, CommandError

from apps.admin_panel.models import AdminUser


def _generate_password(length=16):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = 'Crée un AdminUser avec un mot de passe temporaire aléatoire'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Adresse email de l\'admin')
        parser.add_argument('--name', required=True, help='Nom complet de l\'admin')

    def handle(self, *args, **options):
        email = options['email']
        name = options['name']

        if AdminUser.objects.filter(email=email).exists():
            raise CommandError(f'Un admin avec l\'email {email} existe déjà.')

        password = _generate_password()
        AdminUser.objects.create_admin(
            email=email,
            password=password,
            full_name=name,
            force_password_change=True,
        )

        self.stdout.write(self.style.SUCCESS('\n✅ Admin créé avec succès !\n'))
        self.stdout.write(f'  Email    : {email}')
        self.stdout.write(f'  Password : {password}')
        self.stdout.write(f'  TOTP     : À configurer sur /admin/login (première connexion)')
        self.stdout.write(self.style.WARNING('  IP       : Vérifier que votre IP est dans ADMIN_ALLOWED_IPS\n'))
