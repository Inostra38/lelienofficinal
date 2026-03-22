
from datetime import date as date_type, timedelta
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password, check_password

class Collaborator(models.Model):
    """
    Un membre de l'équipe officinale.
    Il n'a pas de compte utilisateur (User), il "appartient" à une Pharmacie.
    Il s'authentifie ponctuellement via un PIN pour signer des actions.
    """

    class Role(models.TextChoices):
        TITULAIRE = 'Titulaire', _('Titulaire')
        ADJOINT = 'Adjoint', _('Adjoint')
        PREPARATEUR = 'Préparateur', _('Préparateur')
        ETUDIANT = 'Étudiant', _('Étudiant')
        APPRENTI = 'Apprenti', _('Apprenti')

    class Civility(models.TextChoices):
        MR = 'M.', _('M.')
        MME = 'Mme', _('Mme')
        AUTRE = 'Autre', _('Autre')

    # Lien vers l'entité Pharmacie (Auth User)
    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='collaborators',
        verbose_name=_("Pharmacie de rattachement")
    )

    civility = models.CharField(_("Civilité"), max_length=10, choices=Civility.choices, default=Civility.MR)
    first_name = models.CharField(_("Prénom"), max_length=100)
    last_name = models.CharField(_("Nom"), max_length=100)
    role = models.CharField(_("Rôle"), max_length=20, choices=Role.choices, default=Role.PREPARATEUR)

    # Sécurité : On ne stocke JAMAIS le PIN en clair
    pin_hash = models.CharField(_("Hash du PIN"), max_length=128)

    # Email personnel (optionnel, pour contact interne)
    email = models.EmailField(_("Email personnel"), blank=True, null=True)

    # Couleur pour l'identification visuelle
    color = models.CharField(_("Couleur"), max_length=20, default='blue')

    # Permissions fonctionnelles (indépendantes du rôle sauf Titulaire)
    can_manage_account = models.BooleanField(_("Gérer le compte"), default=False)
    can_manage_team = models.BooleanField(_("Gérer l'équipe"), default=False)
    can_manage_planning = models.BooleanField(_("Gérer le planning"), default=False)
    can_manage_quality = models.BooleanField(_("Gérer la qualité"), default=False)
    can_manage_procedures = models.BooleanField(_("Gérer les procédures"), default=False)
    can_publish_procedures = models.BooleanField(_("Publier les procédures"), default=False)
    can_close_nonconformities = models.BooleanField(_("Clôturer les non-conformités"), default=False)
    can_assign_task = models.BooleanField(_("Assigner des tâches"), default=False)

    weekly_hours   = models.DecimalField(
        max_digits=4, decimal_places=1, default=35.0,
        verbose_name="Heures hebdomadaires contractuelles"
    )

    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Date d'archivage"))
    created_at = models.DateTimeField(auto_now_add=True)

    # Ordre d'affichage dans le planning (modifiable par le manager)
    display_order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name = _("Collaborateur")
        verbose_name_plural = _("Collaborateurs")
        # Un collaborateur est unique par pharmacie (évite les doublons de noms)
        unique_together = ('pharmacy', 'first_name', 'last_name')
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        # Le Titulaire a toujours tous les droits — inaltérable
        if self.role == self.Role.TITULAIRE:
            self.can_manage_account = True
            self.can_manage_team = True
            self.can_manage_planning = True
            self.can_manage_quality = True
            self.can_manage_procedures = True
            self.can_publish_procedures = True
            self.can_close_nonconformities = True
            self.can_assign_task = True
        super().save(*args, **kwargs)

    def set_pin(self, raw_pin):
        """Hache le code PIN avant de l'enregistrer."""
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin):
        """Vérifie si le PIN fourni correspond au hash stocké."""
        return check_password(raw_pin, self.pin_hash)

    def active_contract_on(self, target_date: date_type):
        """Retourne le ContractHistory actif à la date donnée, ou None."""
        return self.contracts.filter(
            start_date__lte=target_date
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=target_date)
        ).order_by('-start_date').first()


class ContractHistory(models.Model):
    """Historique des contrats d'un collaborateur."""

    class ContractType(models.TextChoices):
        CDI          = 'CDI',          'CDI'
        CDD          = 'CDD',          'CDD'
        APPRENTISSAGE = 'APPRENTISSAGE', 'Apprentissage'
        INTERIM      = 'INTERIM',      'Intérim'
        TNS          = 'TNS',          'TNS'

    collaborator  = models.ForeignKey(
        Collaborator, on_delete=models.CASCADE, related_name='contracts'
    )
    contract_type = models.CharField(max_length=20, choices=ContractType.choices)
    weekly_hours  = models.DecimalField(max_digits=4, decimal_places=1)
    start_date    = models.DateField()
    end_date      = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        end = self.end_date.isoformat() if self.end_date else 'en cours'
        return f"{self.collaborator} — {self.contract_type} {self.weekly_hours}h ({self.start_date} → {end})"


@receiver(post_save, sender=ContractHistory)
def on_contract_saved(sender, instance, created, **kwargs):
    """
    À la création d'un nouveau contrat :
    - Ferme l'ancien (end_date = start_date - 1 jour)
    - Met à jour weekly_hours sur le collaborateur si le contrat est en cours
    """
    if not created:
        return

    # Fermer le contrat précédent
    ContractHistory.objects.filter(
        collaborator=instance.collaborator,
        end_date__isnull=True,
    ).exclude(pk=instance.pk).update(
        end_date=instance.start_date - timedelta(days=1)
    )

    # Mettre à jour weekly_hours si contrat en cours (pas de end_date ou end_date >= aujourd'hui)
    today = date_type.today()
    if instance.end_date is None or instance.end_date >= today:
        Collaborator.objects.filter(pk=instance.collaborator_id).update(
            weekly_hours=instance.weekly_hours
        )