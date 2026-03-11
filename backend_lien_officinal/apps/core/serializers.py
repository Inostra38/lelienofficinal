from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Pharmacy


class PharmacyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['auth_type'] = 'pharmacy_account'
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Pharmacy
        fields = ['email', 'password', 'password_confirm']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return Pharmacy.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )


class ProfileSetupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = ['nom_officine', 'city', 'siret']

    def validate_nom_officine(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Le nom de l'officine est obligatoire.")
        return value

    def validate_city(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("La ville est obligatoire.")
        return value


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
            'onboarding_completed',
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
