import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


# Régions administratives françaises : 13 métropolitaines + 5 DROM.
# Valeur = libellé (les noms de régions sont stables). Utilisé pour le `choices`
# du champ region et repris à l'identique dans le menu déroulant frontend.
FRENCH_REGIONS = [
    'Auvergne-Rhône-Alpes',
    'Bourgogne-Franche-Comté',
    'Bretagne',
    'Centre-Val de Loire',
    'Corse',
    'Grand Est',
    'Hauts-de-France',
    'Île-de-France',
    'Normandie',
    'Nouvelle-Aquitaine',
    'Occitanie',
    'Pays de la Loire',
    "Provence-Alpes-Côte d'Azur",
    'Guadeloupe',
    'Martinique',
    'Guyane',
    'La Réunion',
    'Mayotte',
]
REGION_CHOICES = [(r, r) for r in FRENCH_REGIONS]


def logo_storage():
    """Stockage du logo de pharmacie : URL signée 7 jours (URLs quasi-stables)
    en prod S3, stockage par défaut (fichiers) en dev. Callable pour rester
    compatible avec les migrations et les deux environnements."""
    from django.conf import settings
    from django.core.files.storage import default_storage
    if getattr(settings, 'SCW_ACCESS_KEY', None):
        from apps.core.storages import LogoStorage
        return LogoStorage()
    return default_storage


class PharmacyManager(BaseUserManager):
    """
    Gestionnaire personnalisé pour créer les Pharmacies.
    On utilise l'email comme identifiant unique, pas le 'username'.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Une adresse email est obligatoire.'))
        email = self.normalize_email(email)
        pharmacy = self.model(email=email, **extra_fields)
        if password:
            pharmacy.set_password(password)
        pharmacy.save(using=self._db)
        return pharmacy

    def create_superuser(self, email, password=None, **extra_fields):
        """Création du SuperAdmin (Toi)"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le Superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le Superuser doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class Pharmacy(AbstractBaseUser, PermissionsMixin):
    """
    L'Entité PHARMACIE (Authentification Principale).
    Remplace le User par défaut de Django.
    """
    email = models.EmailField(_('Adresse Email de connexion'), unique=True)
    nom_officine = models.CharField(_("Nom de l'Officine"), max_length=255)
    siret = models.CharField(_("Numéro SIRET"), max_length=14, unique=True, blank=True, null=True)

    # Adresse détaillée
    address1 = models.CharField(_("Adresse ligne 1"), max_length=255, blank=True)
    address2 = models.CharField(_("Complément d'adresse"), max_length=255, blank=True)
    postal_code = models.CharField(_("Code postal"), max_length=10, blank=True)
    city = models.CharField(_("Ville"), max_length=100, blank=True)
    region = models.CharField(_("Région"), max_length=100, blank=True, choices=REGION_CHOICES)
    country = models.CharField(_("Pays"), max_length=100, default="France")

    # Informations légales
    raison_sociale = models.CharField(_("Raison sociale"), max_length=255, blank=True)
    vat_number = models.CharField(_("Numéro de TVA"), max_length=20, blank=True)

    # Contact — ligne fixe + portable
    phone_fixe = models.CharField(_("Téléphone fixe"), max_length=20, blank=True)
    phone_mobile = models.CharField(_("Téléphone portable"), max_length=20, blank=True)

    # Crédits SMS
    sms_credits = models.PositiveIntegerField(_("Crédits SMS"), default=20)

    # Type de pharmacie
    class PharmacyType(models.TextChoices):
        URBAINE = 'urbaine', _('Urbaine')
        RURALE = 'rurale', _('Rurale')
        CENTRE_BOURG = 'centre-bourg', _('Centre Bourg')
        CENTRE_COMMERCIAL = 'centre-commercial', _('Centre Commercial')

    pharmacy_type = models.CharField(
        _("Type de pharmacie"),
        max_length=20,
        choices=PharmacyType.choices,
        default=PharmacyType.URBAINE,
        blank=True
    )

    # Logo (optionnel)
    logo = models.ImageField(_("Logo"), upload_to='pharmacy_logos/', blank=True, null=True, storage=logo_storage)

    # Email en attente de vérification (structure prête pour Mailgun)
    pending_email = models.EmailField(_("Email en attente"), blank=True, null=True)
    email_verification_token = models.UUIDField(_("Token de vérification email"), blank=True, null=True)
    email_verification_expires = models.DateTimeField(_("Expiration du token"), blank=True, null=True)
    email_verified = models.BooleanField(_("Email vérifié"), default=False)

    # Gestion Premium & Statut
    is_premium = models.BooleanField(_("Abonnement Premium"), default=False)
    is_active = models.BooleanField(default=True)
    onboarding_completed = models.BooleanField(_("Onboarding complété"), default=False)
    is_staff = models.BooleanField(default=False) # Nécessaire pour accéder à l'admin Django
    date_joined = models.DateTimeField(default=timezone.now)

    # Suppression de compte différée + anonymisation RGPD (voir apps/core/account_deletion.py)
    deletion_requested_at  = models.DateTimeField(_("Suppression demandée le"), null=True, blank=True)
    deletion_scheduled_for = models.DateTimeField(_("Suppression programmée pour"), null=True, blank=True)
    anonymized_at          = models.DateTimeField(_("Compte anonymisé le"), null=True, blank=True)

    # Configuration du Manager
    objects = PharmacyManager()

    USERNAME_FIELD = 'email' # On se logue avec l'email
    REQUIRED_FIELDS = ['nom_officine'] # Champs demandés par 'createsuperuser' en plus de l'email

    class Meta:
        verbose_name = _("Pharmacie")
        verbose_name_plural = _("Pharmacies")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sms_credits__gte=0),
                name='pharmacy_sms_credits_non_negative',
            ),
        ]

    def generate_email_verification_token(self):
        """
        Génère un token UUID et une date d'expiration (24h) pour la vérification email.
        TODO: Quand Mailgun sera configuré, envoyer un email de vérification à pending_email
              avec le token, et ne basculer l'email qu'après vérification via
              GET /api/account/verify-email/?token=<uuid>
        """
        self.email_verification_token = uuid.uuid4()
        self.email_verification_expires = timezone.now() + timedelta(hours=24)
        self.save(update_fields=['email_verification_token', 'email_verification_expires'])
        return self.email_verification_token

    def __str__(self):
        return f"{self.nom_officine} ({self.email})"


class PasswordResetToken(models.Model):
    pharmacy = models.ForeignKey(
        'Pharmacy', on_delete=models.CASCADE, related_name='reset_tokens'
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Token réinitialisation mot de passe")

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()

    def __str__(self):
        return f"Reset {self.pharmacy.email} — {'valide' if self.is_valid() else 'expiré/utilisé'}"


class SMSTemplate(models.Model):
    pharmacy = models.ForeignKey(
        'Pharmacy', on_delete=models.CASCADE, related_name='sms_templates'
    )
    title = models.CharField(max_length=50)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pharmacy', 'title')
        verbose_name = "Template SMS"
        verbose_name_plural = "Templates SMS"

    def __str__(self):
        return self.title


class SMSLog(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'PENDING',   "En cours d'envoi"
        SUCCESS   = 'SUCCESS',   'Envoyé'      # rétrocompat données existantes
        DELIVERED = 'DELIVERED', 'Livré'
        FAILED    = 'FAILED',    'Échec'

    pharmacy = models.ForeignKey(
        'Pharmacy', on_delete=models.CASCADE, related_name='sms_logs'
    )
    template = models.ForeignKey(
        SMSTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    sent_by = models.ForeignKey(
        'team.Collaborator', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sms_sent'
    )
    to_hash = models.CharField(max_length=64)
    recipient_civilite = models.CharField(max_length=3, blank=True)
    recipient_name = models.CharField(max_length=200, blank=True)
    motif = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_message_id = models.CharField(max_length=100, blank=True, default='')
    credits_used = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Log SMS"
        verbose_name_plural = "Logs SMS"
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.pharmacy} → {self.recipient_name} {self.status} ({self.sent_at:%Y-%m-%d})"

