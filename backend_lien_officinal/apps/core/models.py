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
    adresse = models.TextField(_("Adresse complète"), blank=True)
    
    # Gestion Premium & Statut
    is_premium = models.BooleanField(_("Abonnement Premium"), default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # Nécessaire pour accéder à l'admin Django
    date_joined = models.DateTimeField(default=timezone.now)

    # Configuration du Manager
    objects = PharmacyManager()

    USERNAME_FIELD = 'email' # On se logue avec l'email
    REQUIRED_FIELDS = ['nom_officine'] # Champs demandés par 'createsuperuser' en plus de l'email

    class Meta:
        verbose_name = _("Pharmacie")
        verbose_name_plural = _("Pharmacies")

    def __str__(self):
        return f"{self.nom_officine} ({self.email})"