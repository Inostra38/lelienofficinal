from rest_framework import serializers
from django.utils import timezone
from apps.team.models import Collaborator
from .models import Shift, AbsenceRequest, PharmacyDayStatus, PlanningSettings, WeekTemplate, TemplateShift, OpeningHours, TimeAdjustment, Constraint


class CollaboratorMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = ['id', 'first_name', 'last_name', 'color', 'role', 'weekly_hours']


# ── Shift ─────────────────────────────────────────────────────────────────────

class ShiftSerializer(serializers.ModelSerializer):
    collaborator = CollaboratorMinimalSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        # La FK existe toujours avec le soft-delete → on peut toujours lire le nom
        if obj.collaborator:
            return f"{obj.collaborator.first_name} {obj.collaborator.last_name}"
        if obj.collaborator_snapshot:
            return obj.collaborator_snapshot
        return "Collaborateur archivé"

    class Meta:
        model = Shift
        fields = [
            'id', 'collaborator', 'collaborator_snapshot', 'display_name',
            'start_datetime', 'end_datetime',
            'is_published', 'is_extra_hour', 'is_absent', 'absence_type', 'note', 'created_at', 'updated_at',
        ]


class ShiftCreateSerializer(serializers.ModelSerializer):
    collaborator_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Shift
        fields = ['collaborator_id', 'start_datetime', 'end_datetime', 'is_extra_hour', 'note']

    def validate_collaborator_id(self, value):
        request = self.context['request']
        try:
            collaborator = Collaborator.objects.get(id=value, pharmacy=request.user, is_active=True)
        except Collaborator.DoesNotExist:
            raise serializers.ValidationError("Collaborateur introuvable.")
        self.context['collaborator'] = collaborator
        return value

    def validate(self, attrs):
        attrs.pop('collaborator_id', None)
        attrs['collaborator'] = self.context['collaborator']
        return attrs

    def create(self, validated_data):
        return Shift.objects.create(**validated_data)


class ShiftUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['start_datetime', 'end_datetime', 'is_extra_hour', 'is_absent', 'absence_type', 'note']


# ── AbsenceRequest ────────────────────────────────────────────────────────────

class AbsenceRequestSerializer(serializers.ModelSerializer):
    collaborator = CollaboratorMinimalSerializer(read_only=True)
    reviewed_by = CollaboratorMinimalSerializer(read_only=True)

    class Meta:
        model = AbsenceRequest
        fields = [
            'id', 'collaborator', 'start_date', 'end_date',
            'type', 'status', 'note', 'created_at', 'reviewed_at', 'reviewed_by',
            'posted_by_manager', 'working_days_count', 'start_period', 'end_period',
        ]


class AbsenceRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbsenceRequest
        fields = ['start_date', 'end_date', 'type', 'note', 'start_period', 'end_period']
        extra_kwargs = {
            'type':         {'required': False},
            'start_period': {'required': False},
            'end_period':   {'required': False},
        }

    def validate(self, attrs):
        start_period = attrs.get('start_period', 'morning')
        end_period   = attrs.get('end_period',   'evening')
        start        = attrs.get('start_date')
        end          = attrs.get('end_date')

        if (start_period == 'afternoon' and end_period == 'morning'
                and start and end and start == end):
            raise serializers.ValidationError(
                'Combinaison impossible : début après-midi et fin matin le même jour.'
            )
        return attrs

    def create(self, validated_data):
        collaborator = self.context['collaborator']
        is_manager   = self.context.get('is_manager', False)
        actor        = self.context.get('actor')

        kwargs = dict(collaborator=collaborator, **validated_data)
        if is_manager:
            kwargs.update(
                status=AbsenceRequest.Status.APPROVED,
                posted_by_manager=True,
                reviewed_by=actor,
                reviewed_at=timezone.now(),
            )
        return AbsenceRequest.objects.create(**kwargs)


# ── PharmacyDayStatus ─────────────────────────────────────────────────────────

class PharmacyDayStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyDayStatus
        fields = ['id', 'date', 'status', 'on_call_day', 'on_call_night', 'note']


# ── PlanningSettings ──────────────────────────────────────────────────────────

class PlanningSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanningSettings
        fields = [
            'draft_window',
            'on_call_day_start', 'on_call_day_end',
            'on_call_night_start', 'on_call_night_end',
            'on_call_sunday',
        ]


# ── OpeningHours ───────────────────────────────────────────────────────────────

class OpeningHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OpeningHours
        fields = ['id', 'day_of_week', 'start_time', 'end_time']


# ── WeekTemplate ──────────────────────────────────────────────────────────────

class TemplateShiftSerializer(serializers.ModelSerializer):
    collaborator = CollaboratorMinimalSerializer(read_only=True)
    collaborator_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TemplateShift
        fields = ['id', 'collaborator', 'collaborator_id', 'day_of_week', 'start_time', 'end_time', 'note']


class WeekTemplateSerializer(serializers.ModelSerializer):
    shifts = TemplateShiftSerializer(many=True, read_only=True)

    class Meta:
        model = WeekTemplate
        fields = ['letter', 'apply_from', 'shifts']


class WeekTemplateListSerializer(serializers.ModelSerializer):
    shift_count = serializers.SerializerMethodField()

    class Meta:
        model = WeekTemplate
        fields = ['letter', 'apply_from', 'shift_count']

    def get_shift_count(self, obj):
        return obj.shifts.count()


# ── TimeAdjustment ────────────────────────────────────────────────────────────

class TimeAdjustmentSerializer(serializers.ModelSerializer):
    collaborator = CollaboratorMinimalSerializer(read_only=True)
    declared_by  = CollaboratorMinimalSerializer(read_only=True)

    class Meta:
        model  = TimeAdjustment
        fields = ['id', 'collaborator', 'date', 'type', 'actual_time', 'reference_time',
                  'duration_minutes', 'shift', 'note', 'declared_by', 'created_at']


class TimeAdjustmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TimeAdjustment
        fields = ['date', 'type', 'actual_time', 'reference_time', 'duration_minutes', 'shift', 'note']


# ── Contraintes planning ───────────────────────────────────────────────────────

class ConstraintSerializer(serializers.ModelSerializer):
    collaborator_name = serializers.SerializerMethodField()

    def get_collaborator_name(self, obj):
        if obj.collaborator:
            return f"{obj.collaborator.first_name} {obj.collaborator.last_name}"
        return None

    class Meta:
        model = Constraint
        fields = ['id', 'level', 'collaborator', 'collaborator_name',
                  'description', 'is_active', 'order']
        read_only_fields = ['id', 'collaborator_name']
