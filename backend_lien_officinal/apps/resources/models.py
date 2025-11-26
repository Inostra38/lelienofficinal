from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    nom = models.CharField(_("Nom de la catégorie"), max_length=50)
    icon_slug = models.CharField(_("Icône"), max_length=50, default="folder")
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ['ordre']

    def __str__(self):
        return self.nom

class ResourceCard(models.Model):
    """
    Le conteneur principal (La fiche 'Ameli' ou 'Biogaran').
    """
    TYPE_CHOICES = [
        ('OFFICIAL', 'Officiel (Validé Admin)'),
        ('PARTNER', 'Partenaire (Géré par Labo)'),
        ('PRIVATE', 'Privé (Créé par Pharmacie)'),
    ]

    category = models.ForeignKey(
        'Category', 
        on_delete=models.SET_NULL,  # Rendu optionnel pour les Cartes Officielles
        null=True,                 
        blank=True,                
        related_name='cards',
        verbose_name=_("Catégorie d'affichage par défaut")
    )

    titre = models.CharField(_("Titre de la carte"), max_length=100)
    description_officielle = models.TextField(_("Description officielle"), blank=True)
    logo = models.ImageField(upload_to='cards/logos/', blank=True, null=True)
    
    type = models.CharField(_("Type de carte"), max_length=20, choices=TYPE_CHOICES, default='OFFICIAL')
    
    owner_partner = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True)
    owner_pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='owned_cards'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Carte de Ressource")
        verbose_name_plural = _("Cartes de Ressources")

    def __str__(self):
        return self.titre

class ResourceItem(models.Model):
    """
    Les sous-éléments cliquables (Lien Web, PDF, Téléphone...)
    """
    TYPE_CHOICES = [
        ('WEB', 'Site Web'),
        ('PDF', 'Document PDF'),
        ('TEL', 'Numéro de téléphone'),
        ('MAIL', 'Adresse Email'),
    ]

    card = models.ForeignKey(ResourceCard, on_delete=models.CASCADE, related_name='items')
    type = models.CharField(_("Type d'élément"), max_length=10, choices=TYPE_CHOICES, default='WEB')
    label = models.CharField(_("Libellé du lien"), max_length=100)
    
    url = models.CharField(max_length=500, blank=True)
    file = models.FileField(upload_to='cards/files/', blank=True, null=True)
    
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='owned_items'
    )
    
    ordre = models.PositiveIntegerField(default=0)

    @property
    def final_url(self):
        if self.file:
            return self.file.url
        return self.url

    class Meta:
        verbose_name = _("Élément de Ressource")
        verbose_name_plural = _("Éléments de Ressources")

    def __str__(self):
        return self.label

class PharmacyPreference(models.Model):
    """
    La couche de personnalisation par pharmacie sur une carte.
    """
    pharmacy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card = models.ForeignKey(ResourceCard, on_delete=models.CASCADE, related_name='preferences')
    
    is_favorite = models.BooleanField(default=False)
    notes_perso = models.TextField(_("Notes Privées"), blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Préférence Pharmacie")
        verbose_name_plural = _("Préférences Pharmacies")
        unique_together = ('pharmacy', 'card')
        
    def __str__(self):
        return f"Préf. pour {self.card.titre} par {self.pharmacy.nom_officine}"