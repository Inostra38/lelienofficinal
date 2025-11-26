from rest_framework import serializers
from .models import Category, ResourceCard, ResourceItem, PharmacyPreference
from apps.partners.models import Partner
from django.db.models import Prefetch

# =====================================================
# 1. SERIALIZERS BASES ET ITEMS
# =====================================================

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

# =====================================================
# 2. SERIALIZERS ADOPTÉS (Les vues spéciales)
# =====================================================

class AdoptedCardSerializer(serializers.ModelSerializer):
    """Sérialise une carte adoptée (lecture seule)"""
    items = ResourceItemSerializer(many=True, read_only=True)
    partner = PartnerSerializer(source='owner_partner', read_only=True)
    
    class Meta:
        model = ResourceCard
        fields = ['id', 'titre', 'description_officielle', 'logo', 'type', 'items', 'partner']

class ResourceCardSerializer(serializers.ModelSerializer):
    """
    Serializer pour la gestion des cartes CRUD (principalement Privées).
    """
    items = ResourceItemSerializer(many=True, read_only=True)
    partner = PartnerSerializer(source='owner_partner', read_only=True)
    is_favorite = serializers.BooleanField(default=False, read_only=True)
    notes_perso = serializers.CharField(default="", read_only=True)

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        required=True # Requis pour la création, mais non pour l'assignation (géré par le views.py)
    )
    
    class Meta:
        model = ResourceCard
        fields = [
            'id', 'titre', 'description_officielle', 'logo', 'type', 
            'items', 'partner', 'is_favorite', 'notes_perso', 
            'category'
        ]
        extra_kwargs = {
            'type': {'read_only': True},
            'description_officielle': {'required': False},
            'logo': {'required': False},
        }

# =====================================================
# 3. LE SERIALIZER DE CATÉGORIE (Le Conteneur Final)
# =====================================================

class CategorySerializer(serializers.ModelSerializer):
    """
    Le serializer qui organise le dashboard.
    """
    cards = ResourceCardSerializer(many=True, read_only=True)
    
    # 🔥 FIX CRITIQUE : Permet de récupérer les cartes adoptées dans la catégorie
    adopted_cards = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre', 'cards', 'adopted_cards']

    def get_adopted_cards(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        
        # Récupère les préférences de l'utilisateur pour cette catégorie
        preferences = PharmacyPreference.objects.filter(
            pharmacy=request.user,
            assigned_category=obj
        ).select_related('card__owner_partner').prefetch_related('card__items')

        adopted = []
        for pref in preferences:
            # On sérialise la carte en utilisant le AdoptedCardSerializer
            card_data = AdoptedCardSerializer(pref.card).data
            
            # On ajoute les données de la préférence (notes, favori)
            card_data['is_favorite'] = pref.is_favorite
            card_data['notes_perso'] = pref.notes_perso
            card_data['is_adopted'] = True
            adopted.append(card_data)
        
        return adopted

class CatalogCardSerializer(serializers.ModelSerializer):
    """
    Serializer léger pour la liste de choix dans la modale d'ajout.
    """
    class Meta:
        model = ResourceCard
        fields = ['id', 'titre', 'logo', 'description_officielle', 'type']