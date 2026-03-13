from rest_framework import serializers
from .models import Task
from apps.team.models import Collaborator


class CollaboratorMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = ['id', 'first_name', 'last_name', 'color']


class TaskSerializer(serializers.ModelSerializer):
    created_by = CollaboratorMinimalSerializer(read_only=True)
    assigned_to = CollaboratorMinimalSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'priority', 'status', 'type',
            'created_by', 'assigned_to', 'due_date', 'completed_at',
            'is_completion_seen', 'order', 'created_at', 'updated_at'
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    assigned_to_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Task
        fields = ['assigned_to_id', 'title', 'description', 'priority', 'due_date']

    def validate_assigned_to_id(self, value):
        if value is None:
            return value
        request = self.context['request']
        try:
            assignee = Collaborator.objects.get(id=value, pharmacy=request.user, is_active=True)
        except Collaborator.DoesNotExist:
            raise serializers.ValidationError("Collaborateur assigné introuvable ou non autorisé.")
        self.context['assignee'] = assignee
        return value

    def create(self, validated_data):
        validated_data.pop('assigned_to_id', None)
        creator = self.context['creator']
        assignee = self.context.get('assignee')
        task_type = Task.TaskType.ASSIGNED if assignee else Task.TaskType.PERSONAL
        return Task.objects.create(
            pharmacy=self.context['request'].user,
            created_by=creator,
            assigned_to=assignee,
            type=task_type,
            **validated_data
        )


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'due_date']
