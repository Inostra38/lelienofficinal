from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class WizardCategory(models.Model):
    """
    Catégories globales de la plateforme, proposées lors de l'onboarding.
    Non liées à une pharmacie — partagées entre tous les utilisateurs.
    """
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    ordre = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Catégorie Wizard")
        verbose_name_plural = _("Catégories Wizard")
        ordering = ['ordre']

    def __str__(self):
        return self.nom


class Category(models.Model):
    nom = models.CharField(_("Nom de la catégorie"), max_length=50)
    ordre = models.PositiveIntegerField(default=0)
    
    owner_pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name=_("Pharmacie propriétaire")
    )

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ['ordre']
        unique_together = ('owner_pharmacy', 'nom')

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
        on_delete=models.CASCADE,
        null=True,                 
        blank=True,                
        related_name='cards',
        verbose_name=_("Catégorie d'affichage par défaut")
    )

    titre = models.CharField(_("Titre de la carte"), max_length=100)
    description_officielle = models.TextField(_("Description officielle"), blank=True)
    type = models.CharField(_("Type de carte"), max_length=20, choices=TYPE_CHOICES, default='PRIVATE')
    
    owner_partner = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL, null=True, blank=True)
    owner_pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='owned_cards'
    )

    icon = models.ImageField(
        _("Icône"),
        upload_to='cards/icons/',
        null=True,
        blank=True,
        help_text=_("Icône carrée représentant la ressource (PNG/SVG recommandé, fond transparent).")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    ordre = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(
        _("Mise en avant"),
        default=False,
        help_text=_("Cocher pour afficher cette ressource en tête de liste.")
    )

    # --- Recommandation communautaire ---
    recommended_to_community = models.BooleanField(
        _("Recommandé à la communauté"),
        default=False,
    )
    recommended_at = models.DateTimeField(
        _("Date de recommandation"),
        null=True,
        blank=True,
    )
    recommended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_cards',
        verbose_name=_("Recommandé par"),
    )
    recommendation_status = models.CharField(
        _("Statut recommandation"),
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('APPROVED', 'Approuvée'),
            ('REJECTED', 'Rejetée'),
        ],
        default='PENDING',
    )

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

    # --- Recommandation communautaire ---
    recommended_to_community = models.BooleanField(
        _("Recommandé à la communauté"),
        default=False,
    )
    recommended_at = models.DateTimeField(
        _("Date de recommandation"),
        null=True,
        blank=True,
    )
    recommended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_items',
        verbose_name=_("Recommandé par"),
    )
    recommendation_status = models.CharField(
        _("Statut recommandation"),
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('APPROVED', 'Approuvée'),
            ('REJECTED', 'Rejetée'),
        ],
        default='PENDING',
    )
    target_official_card = models.ForeignKey(
        'ResourceCard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_community_items',
        verbose_name=_("Carte OFFICIAL cible"),
        help_text=_("Carte OFFICIAL sur laquelle rattacher cet item après approbation"),
    )

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
    
    assigned_category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adopted_preferences',
        verbose_name=_("Catégorie assignée par le pharmacien")
    )
    
    is_favorite = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)
    
    # ✅ NOUVEAU : Deux champs distincts pour les notes
    note_courte = models.CharField(
        _("Note courte (mémo rapide)"),
        max_length=150,
        blank=True,
        default="",
        help_text="Affichée sur la carte (max 150 caractères)"
    )
    note_longue = models.TextField(
        _("Note longue (détails)"),
        blank=True,
        default="",
        help_text="Notes détaillées, procédures, informations..."
    )
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Préférence Pharmacie")
        verbose_name_plural = _("Préférences Pharmacies")
        unique_together = ('pharmacy', 'card')
        
    def __str__(self):
        return f"Préf. pour {self.card.titre} par {self.pharmacy.nom_officine}"