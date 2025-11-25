from django.db import models
from django.utils.translation import gettext_lazy as _

class Partner(models.Model):
    """
    Un Partenaire (Laboratoire, Grossiste, Prestataire...).
    Il paiera pour des pubs et pourra pousser des liens officiels.
    """
    nom = models.CharField(_("Nom du Partenaire"), max_length=100)
    logo = models.ImageField(upload_to='partners/logos/', blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    email_contact = models.EmailField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Partenaire")
        verbose_name_plural = _("Partenaires")

    def __str__(self):
        return self.nom