from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Pharmacy


class LogoValidationMixin:
    """S17 : le logo pharmacie ne passait par aucune validation d'upload → un
    SVG/HTML pouvait être stocké (vecteur XSS servi ensuite). On applique la même
    allowlist type/extension/taille que les autres téléversements."""

    def validate_logo(self, value):
        if value:
            from apps.core.upload_validation import (
                validate_upload, ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTENSIONS,
            )
            try:
                validate_upload(
                    value,
                    allowed_types=ALLOWED_IMAGE_TYPES,
                    allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
                )
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.messages)
        return value


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

    def validate_password(self, value):
        # F1 : appliquer les validateurs Django (AUTH_PASSWORD_VALIDATORS) comme
        # les flux reset/change — bloque les mots de passe faibles (12345678,
        # mots de passe communs, etc.). Avant, seule min_length=8 s'appliquait.
        from django.contrib.auth.password_validation import validate_password as dj_validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            dj_validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

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


class PharmacySerializer(LogoValidationMixin, serializers.ModelSerializer):
    """Serializer pour les informations de la pharmacie"""

    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'email',
            'nom_officine',
            'raison_sociale',
            'siret',
            'address1',
            'address2',
            'postal_code',
            'city',
            'region',
            'country',
            'vat_number',
            'phone_fixe',
            'phone_mobile',
            'pharmacy_type',
            'logo',
            'is_premium',
            'sms_credits',
            'onboarding_completed',
            'email_verified',
            'pending_email',
            'date_joined',
            'deletion_scheduled_for',
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'is_premium', 'sms_credits', 'email_verified', 'pending_email', 'deletion_scheduled_for']


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(min_length=8, write_only=True)


class PharmacyUpdateSerializer(LogoValidationMixin, serializers.ModelSerializer):
    """Serializer pour mettre à jour les informations de la pharmacie"""

    class Meta:
        model = Pharmacy
        fields = [
            'nom_officine',
            'raison_sociale',
            'siret',
            'address1',
            'address2',
            'postal_code',
            'city',
            'region',
            'country',
            'vat_number',
            'phone_fixe',
            'phone_mobile',
            'pharmacy_type',
            'logo'
        ]
