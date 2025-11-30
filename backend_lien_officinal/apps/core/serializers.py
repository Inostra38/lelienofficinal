from rest_framework import serializers
from .models import Pharmacy


class PharmacySerializer(serializers.ModelSerializer):
    """Serializer pour les informations de la pharmacie"""

    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'email',
            'nom_officine',
            'siret',
            'address1',
            'address2',
            'postal_code',
            'city',
            'region',
            'country',
            'vat_number',
            'pharmacy_type',
            'logo',
            'is_premium',
            'date_joined'
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'is_premium']


class PharmacyUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour les informations de la pharmacie"""

    class Meta:
        model = Pharmacy
        fields = [
            'nom_officine',
            'siret',
            'address1',
            'address2',
            'postal_code',
            'city',
            'region',
            'country',
            'vat_number',
            'pharmacy_type',
            'logo'
        ]
