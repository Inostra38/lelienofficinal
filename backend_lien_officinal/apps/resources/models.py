from django.db import models
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
    """
    Les cartes cliquables (Le coeur du dashboard).
    """
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='links',
        verbose_name=_("Catégorie")
    )
    
    # Relation optionnelle : Un lien peut être sponsorisé par un Labo
    partner = models.ForeignKey(
        'partners.Partner', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sponsored_links',
        verbose_name=_("Partenaire associé (Optionnel)")
    )

    titre = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    url = models.URLField(_("URL de destination"))
    
    image = models.ImageField(
        upload_to='links/icons/', 
        blank=True, 
        null=True,
        help_text="Picto ou logo spécifique pour ce lien"
    )

    is_public = models.BooleanField(default=True, help_text="Si faux, invisible pour les pharmacies non-premium (exemple)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Lien")
        verbose_name_plural = _("Liens")

    def __str__(self):
        return self.titre