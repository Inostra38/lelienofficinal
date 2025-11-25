from rest_framework import serializers
from .models import Category, Link
from apps.partners.models import Partner

class PartnerSerializer(serializers.ModelSerializer):
    """Pour afficher le logo du labo à côté du lien"""
    class Meta:
        model = Partner
        fields = ['id', 'nom', 'logo']

class LinkSerializer(serializers.ModelSerializer):
    partner = PartnerSerializer(read_only=True) # On imbrique le partenaire complet

    class Meta:
        model = Link
        fields = ['id', 'titre', 'description', 'url', 'image', 'partner', 'is_public']

class CategorySerializer(serializers.ModelSerializer):
    # Astuce UX : On renvoie directement les liens rangés dans la catégorie
    links = LinkSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre', 'links']