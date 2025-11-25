from rest_framework import serializers
from .models import Category, Link
from apps.partners.models import Partner

# 1. Sérialiseur pour les Partenaires (Labos)
class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ['id', 'nom', 'logo']

# 2. Sérialiseur pour les Liens (avec URL calculée pour les fichiers)
class LinkSerializer(serializers.ModelSerializer):
    partner = PartnerSerializer(read_only=True)
    url = serializers.CharField(source='final_url', read_only=True)

    class Meta:
        model = Link
        # 👇 AJOUTE 'category' DANS CETTE LISTE 👇
        fields = ['id', 'titre', 'description', 'url', 'image', 'partner', 'is_public', 'document', 'category']

# 3. Sérialiseur pour les Catégories (Contenant les liens)
class CategorySerializer(serializers.ModelSerializer):
    # On inclut les liens directement dans la catégorie
    links = LinkSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre', 'links']