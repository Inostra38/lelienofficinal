from rest_framework import serializers
from apps.resources.models import ResourceCard, ResourceItem


class RecommendationCardSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = ResourceCard
        fields = [
            'id', 'titre', 'description_officielle', 'type',
            'recommended_at', 'recommendation_status',
            'pharmacy_name', 'items_count',
        ]

    def get_pharmacy_name(self, obj):
        return str(obj.owner_pharmacy) if obj.owner_pharmacy else None

    def get_items_count(self, obj):
        return obj.items.count()


class RecommendationItemSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.SerializerMethodField()
    parent_card_titre = serializers.SerializerMethodField()
    target_card_titre = serializers.SerializerMethodField()

    class Meta:
        model = ResourceItem
        fields = [
            'id', 'label', 'type', 'url', 'file',
            'recommended_at', 'recommendation_status',
            'pharmacy_name', 'parent_card_titre', 'target_card_titre',
        ]

    def get_pharmacy_name(self, obj):
        if obj.card and obj.card.owner_pharmacy:
            return str(obj.card.owner_pharmacy)
        return None

    def get_parent_card_titre(self, obj):
        return obj.card.titre if obj.card else None

    def get_target_card_titre(self, obj):
        return obj.target_official_card.titre if obj.target_official_card else None
