from rest_framework import serializers
from .models import Collaborator


class CollaboratorSerializer(serializers.ModelSerializer):
    """Serializer pour lire les collaborateurs"""
    pin = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Collaborator
        fields = ['id', 'civility', 'first_name', 'last_name', 'role', 'color', 'is_active', 'created_at', 'pin']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        pin = validated_data.pop('pin', None)
        collaborator = Collaborator(**validated_data)
        if pin:
            collaborator.set_pin(pin)
        collaborator.save()
        return collaborator

    def update(self, instance, validated_data):
        pin = validated_data.pop('pin', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if pin:
            instance.set_pin(pin)
        instance.save()
        return instance


class CollaboratorCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un collaborateur avec PIN"""
    pin = serializers.CharField(write_only=True, required=True, min_length=4, max_length=6)

    class Meta:
        model = Collaborator
        fields = ['civility', 'first_name', 'last_name', 'role', 'color', 'pin']

    def create(self, validated_data):
        pin = validated_data.pop('pin')
        collaborator = Collaborator(**validated_data)
        collaborator.set_pin(pin)
        collaborator.save()
        return collaborator


class PinVerificationSerializer(serializers.Serializer):
    collaborator_id = serializers.IntegerField()
    pin_code = serializers.CharField(max_length=10)