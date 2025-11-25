from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    """
    Les onglets du Dashboard (ex: 'Mes Favoris', 'Laboratoires', 'Outils Comptoir').
    """
    nom = models.CharField(_("Nom de la catégorie"), max_length=50)
    icon_slug = models.CharField(
        _("Nom de l'icône"), 
        max_length=50, 
        help_text="Nom de l'icône dans la librairie Frontend (ex: 'flask', 'heart')",
        default="link"
    )
    ordre = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage (0 = premier)")

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Link(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='links')
    
    # NOUVEAU : Propriétaire (Si NULL = Lien Global Public, Si Rempli = Lien Privé)
    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='custom_links'
    )

    partner = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True)
    titre = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    
    # URL ou Fichier
    url = models.CharField(max_length=500, blank=True) # On passe en CharField pour être souple
    document = models.FileField(upload_to='pharmacy_docs/', blank=True, null=True) # Pour les PDF

    image = models.ImageField(upload_to='links/icons/', blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Si c'est un lien privé (pharmacy set), il n'est pas public globalement
        if self.pharmacy:
            self.is_public = False
        super().save(*args, **kwargs)

    @property
    def final_url(self):
        # Si c'est un document, l'URL est le chemin du fichier
        if self.document:
            return self.document.url
        return self.url

    def __str__(self):
        return self.titre