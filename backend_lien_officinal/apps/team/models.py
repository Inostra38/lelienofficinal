
from django.db import models
from django.conf import settings
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

    # Couleur pour l'identification visuelle
    color = models.CharField(_("Couleur"), max_length=20, default='blue')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Collaborateur")
        verbose_name_plural = _("Collaborateurs")
        # Un collaborateur est unique par pharmacie (évite les doublons de noms)
        unique_together = ('pharmacy', 'first_name', 'last_name')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    def set_pin(self, raw_pin):
        """Hache le code PIN avant de l'enregistrer."""
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin):
        """Vérifie si le PIN fourni correspond au hash stocké."""
        return check_password(raw_pin, self.pin_hash)