from rest_framework import serializers
from .models import Collaborator

PERMISSION_FIELDS = [
    'can_manage_account', 'can_manage_team', 'can_manage_planning', 'can_manage_quality',
    'can_manage_procedures', 'can_publish_procedures', 'can_close_nonconformities', 'can_assign_task',
]


class CollaboratorSerializer(serializers.ModelSerializer):
    """Serializer pour lire et mettre à jour les collaborateurs"""
    pin = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Collaborator
        fields = [
            'id', 'civility', 'first_name', 'last_name', 'role', 'email', 'color',
            'is_active', 'archived_at', 'created_at', 'pin',
            'can_manage_account', 'can_manage_team', 'can_manage_planning', 'can_manage_quality',
            'can_manage_procedures', 'can_publish_procedures', 'can_close_nonconformities', 'can_assign_task',
            'contract_type', 'weekly_hours',
        ]
        read_only_fields = ['id', 'created_at', 'archived_at']

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
        fields = [
            'civility', 'first_name', 'last_name', 'role', 'email', 'color', 'pin',
            'can_manage_account', 'can_manage_team', 'can_manage_planning', 'can_manage_quality',
            'can_manage_procedures', 'can_publish_procedures', 'can_close_nonconformities', 'can_assign_task',
        ]

    def create(self, validated_data):
        pin = validated_data.pop('pin')
        collaborator = Collaborator(**validated_data)
        collaborator.set_pin(pin)
        collaborator.save()
        return collaborator


class CollaboratorPermissionsSerializer(serializers.ModelSerializer):
    """Serializer dédié à la modification des permissions (endpoint /permissions/)"""

    class Meta:
        model = Collaborator
        fields = PERMISSION_FIELDS


class PinVerificationSerializer(serializers.Serializer):
    collaborator_id = serializers.IntegerField()
    pin_code = serializers.CharField(max_length=10)
