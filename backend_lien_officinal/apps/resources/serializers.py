from rest_framework import serializers
from .models import Category, ResourceCard, ResourceItem, PharmacyPreference
from apps.partners.models import Partner

class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ['id', 'nom', 'logo']

class ResourceItemSerializer(serializers.ModelSerializer):
    final_url = serializers.SerializerMethodField()

    class Meta:
        model = ResourceItem
        fields = ['id', 'type', 'label', 'url', 'file', 'final_url', 'ordre', 'card', 'owner']
        extra_kwargs = {
            'file': {'required': False},
            'url': {'required': False},
            'owner': {'read_only': True} 
        }

    def get_final_url(self, obj):
        if obj.file:
            return obj.file.url
        return obj.url

class ResourceCardSerializer(serializers.ModelSerializer):
    items = ResourceItemSerializer(many=True, read_only=True)
    partner = PartnerSerializer(source='owner_partner', read_only=True)
    is_favorite = serializers.BooleanField(default=False, read_only=True)
    notes_perso = serializers.CharField(default="", read_only=True)

    class Meta:
        model = ResourceCard
        fields = [
            'id', 'titre', 'description_officielle', 'logo', 'type', 
            'items', 'partner', 'is_favorite', 'notes_perso'
        ]

class CategorySerializer(serializers.ModelSerializer):
    cards = ResourceCardSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre', 'cards']

# 👇 SERIALIZER POUR LE CATALOGUE (Liste les Cartes disponibles)
class CatalogCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceCard
        fields = ['id', 'titre', 'logo', 'description_officielle', 'type']