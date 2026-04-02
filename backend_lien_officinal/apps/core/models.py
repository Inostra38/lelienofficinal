import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

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
    region = models.CharField(_("Région"), max_length=100, blank=True)
    country = models.CharField(_("Pays"), max_length=100, default="France")

    # Informations légales
    vat_number = models.CharField(_("Numéro de TVA"), max_length=20, blank=True)

    # Contact
    phone = models.CharField(_("Téléphone"), max_length=20, blank=True)

    # Crédits SMS
    sms_credits = models.PositiveIntegerField(_("Crédits SMS"), default=0)

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
    logo = models.ImageField(_("Logo"), upload_to='pharmacy_logos/', blank=True, null=True)

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

