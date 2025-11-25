from rest_framework import serializers
from .models import Collaborator

class CollaboratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = ['id', 'first_name', 'last_name', 'role']

class PinVerificationSerializer(serializers.Serializer):
    collaborator_id = serializers.IntegerField()
    pin_code = serializers.CharField(max_length=10)