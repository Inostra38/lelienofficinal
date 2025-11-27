from rest_framework import serializers
from .models import Category, ResourceCard, ResourceItem, PharmacyPreference
from apps.partners.models import Partner
from django.conf import settings

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
            return f"{settings.BACKEND_BASE_URL}{obj.file.url}"
        
        url = obj.url or ''
        if not url:
            return ''
        
        if not url.startswith(('http://', 'https://', 'tel:', 'mailto:')):
            return 'https://' + url
        
        return url


# =====================================================
# 2. SERIALIZERS CARTES
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
    is_favorite = serializers.SerializerMethodField()
    note_courte = serializers.SerializerMethodField()
    note_longue = serializers.SerializerMethodField()

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        required=True
    )
    
    class Meta:
        model = ResourceCard
        fields = [
            'id', 'titre', 'description_officielle', 'logo', 'type', 
            'items', 'partner', 'is_favorite', 'note_courte', 'note_longue',
            'category'
        ]
        extra_kwargs = {
            'type': {'read_only': True},
            'description_officielle': {'required': False},
            'logo': {'required': False},
        }

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        preference = PharmacyPreference.objects.filter(
            pharmacy=request.user,
            card=obj
        ).first()
        
        return preference.is_favorite if preference else False

    def get_note_courte(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return ""
        
        preference = PharmacyPreference.objects.filter(
            pharmacy=request.user,
            card=obj
        ).first()
        
        return preference.note_courte if preference else ""

    def get_note_longue(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return ""
        
        preference = PharmacyPreference.objects.filter(
            pharmacy=request.user,
            card=obj
        ).first()
        
        return preference.note_longue if preference else ""


class CatalogCardSerializer(serializers.ModelSerializer):
    """
    Serializer léger pour la liste de choix dans la modale d'ajout.
    """
    class Meta:
        model = ResourceCard
        fields = ['id', 'titre', 'logo', 'description_officielle', 'type']


# =====================================================
# 3. SERIALIZER CATÉGORIE (CRUD COMPLET)
# =====================================================

class CategorySerializer(serializers.ModelSerializer):
    """
    Le serializer qui organise le dashboard + permet CRUD.
    """
    cards = ResourceCardSerializer(many=True, read_only=True)
    adopted_cards = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre', 'cards', 'adopted_cards']
        extra_kwargs = {
            'icon_slug': {'required': False},
            'ordre': {'required': False},
        }

    def get_adopted_cards(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        
        preferences = PharmacyPreference.objects.filter(
            pharmacy=request.user,
            assigned_category=obj
        ).select_related('card__owner_partner').prefetch_related('card__items')

        adopted = []
        for pref in preferences:
            card_data = AdoptedCardSerializer(pref.card).data
            card_data['is_favorite'] = pref.is_favorite
            card_data['note_courte'] = pref.note_courte  # ✅ Accès direct
            card_data['note_longue'] = pref.note_longue  # ✅ Accès direct
            card_data['is_adopted'] = True
            adopted.append(card_data)
        
        return adopted


class CategoryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer simplifié pour la création de catégorie.
    """
    class Meta:
        model = Category
        fields = ['id', 'nom', 'icon_slug', 'ordre']
        extra_kwargs = {
            'icon_slug': {'required': False},
            'ordre': {'required': False},
        }