from rest_framework import serializers
from .utils import sanitize_quill_html
from .models import (
    Procedure, ProcedureAttachment, ProcedureImage, NonConformity,
    CorrectiveAction, ProcedureGroup, ProcedureVersion, ProcedureCategory,
)
from apps.team.models import Collaborator


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collab_repr(collab):
    """Retourne un dict {id, full_name, color} ou None."""
    if collab is None:
        return None
    return {
        'id': collab.id,
        'full_name': f"{collab.first_name} {collab.last_name}",
        'color': collab.color or '',
    }


def _collab_list_repr(collabs):
    """Retourne une liste de dicts {id, full_name, initials, color}."""
    result = []
    for c in collabs.all():
        initials = (
            (c.first_name[:1] if c.first_name else '') +
            (c.last_name[:1] if c.last_name else '')
        ).upper()
        result.append({
            'id': c.id,
            'full_name': f"{c.first_name} {c.last_name}",
            'initials': initials,
            'color': c.color or '',
        })
    return result


# ── ProcedureCategory ─────────────────────────────────────────────────────────

class ProcedureCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureCategory
        fields = ['id', 'name', 'color']
        read_only_fields = ['id']


# ── Attachments & Images ──────────────────────────────────────────────────────

class ProcedureAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureAttachment
        fields = ['id', 'filename', 'original_name', 'file', 'file_type', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ProcedureImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProcedureImage
        fields = ['id', 'image', 'url', 'uploaded_at']
        read_only_fields = ['id', 'url', 'uploaded_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if request and obj.image:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


class ProcedureVersionSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = ProcedureVersion
        fields = ['id', 'version_number', 'content', 'change_summary', 'created_by', 'created_at']

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)


# ── ProcedureGroup ────────────────────────────────────────────────────────────

class ProcedureGroupSerializer(serializers.ModelSerializer):
    procedure_count = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = ProcedureGroup
        fields = ['id', 'name', 'description', 'color', 'order', 'procedure_count', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)


# ── Procedure — List (léger) ──────────────────────────────────────────────────

class ProcedureListSerializer(serializers.ModelSerializer):
    pilots = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    archived_by = serializers.SerializerMethodField()
    group = serializers.PrimaryKeyRelatedField(read_only=True)
    group_name = serializers.SerializerMethodField()
    last_published_version = serializers.IntegerField(read_only=True, allow_null=True)
    is_unread = serializers.BooleanField(read_only=True)

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'categories', 'status',
            'version', 'position', 'parent_id', 'group', 'group_name', 'pilots',
            'updated_at', 'archived_at', 'archived_by', 'last_published_version', 'next_review_date',
            'is_unread',
        ]

    def get_pilots(self, obj):
        return _collab_list_repr(obj.pilots)

    def get_categories(self, obj):
        return ProcedureCategorySerializer(obj.categories.all(), many=True).data

    def get_archived_by(self, obj):
        return _collab_repr(obj.archived_by)

    def get_group_name(self, obj):
        return obj.group.name if obj.group_id else None


# ── Procedure — Detail (complet) ─────────────────────────────────────────────

class ProcedureDetailSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(max_length=20, allow_null=True, allow_blank=True, required=False, default=None)
    pilots = serializers.SerializerMethodField()
    pilot_ids = serializers.PrimaryKeyRelatedField(
        source='pilots',
        queryset=Collaborator.objects.all(),
        many=True,
        write_only=True,
        required=False,
        default=list,
    )
    categories = serializers.SerializerMethodField()
    category_ids = serializers.PrimaryKeyRelatedField(
        source='categories',
        queryset=ProcedureCategory.objects.all(),
        many=True,
        write_only=True,
        required=False,
        default=list,
    )
    created_by = serializers.SerializerMethodField()
    archived_by = serializers.SerializerMethodField()
    group = serializers.PrimaryKeyRelatedField(
        queryset=ProcedureGroup.objects.all(),
        allow_null=True,
        required=False,
    )
    attachments = ProcedureAttachmentSerializer(many=True, read_only=True)
    images = ProcedureImageSerializer(many=True, read_only=True)
    history = ProcedureVersionSerializer(many=True, read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sécurité multi-tenant : borner les cibles assignables à la pharmacie
        # courante. Sans ce filtre (queryset=…objects.all()), un id de
        # collaborateur / catégorie / groupe d'une AUTRE officine pouvait être
        # attaché à une procédure, puis son nom/prénom relu via get_pilots →
        # fuite de données personnelles inter-clients.
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated:
            pharmacy = request.user
            self.fields['pilot_ids'].child_relation.queryset = (
                Collaborator.objects.filter(pharmacy=pharmacy)
            )
            self.fields['category_ids'].child_relation.queryset = (
                ProcedureCategory.objects.filter(pharmacy=pharmacy)
            )
            self.fields['group'].queryset = (
                ProcedureGroup.objects.filter(pharmacy=pharmacy)
            )

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'categories', 'category_ids', 'status',
            'version', 'position', 'group', 'pilots', 'pilot_ids', 'updated_at',
            'content', 'created_by', 'created_at', 'archived_by', 'archived_at',
            'next_review_date', 'attachments', 'images', 'history',
        ]
        # S01/Q11 : status et version ne doivent PAS être modifiables par un
        # PATCH direct — les transitions passent par les actions dédiées
        # (publish/archive, qui écrivent status en bypassant le serializer) et
        # l'incrément de version par le versioning. Sans ça, un éditeur sans
        # droit de publication pouvait fixer status='published' via PATCH.
        read_only_fields = ['status', 'version', 'archived_at']
        validators = []  # Gestion manuelle pour l'unicité de la référence

    def get_pilots(self, obj):
        return _collab_list_repr(obj.pilots)

    def get_categories(self, obj):
        return ProcedureCategorySerializer(obj.categories.all(), many=True).data

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)

    def get_archived_by(self, obj):
        return _collab_repr(obj.archived_by)

    def create(self, validated_data):
        pilots = validated_data.pop('pilots', [])
        categories = validated_data.pop('categories', [])
        instance = super().create(validated_data)
        instance.pilots.set(pilots)
        instance.categories.set(categories)
        return instance

    def update(self, instance, validated_data):
        pilots = validated_data.pop('pilots', None)
        categories = validated_data.pop('categories', None)
        instance = super().update(instance, validated_data)
        if pilots is not None:
            instance.pilots.set(pilots)
        if categories is not None:
            instance.categories.set(categories)
        return instance

    def validate(self, data):
        reference = data.get('reference', getattr(self.instance, 'reference', None))

        # Unicité de la référence (uniquement si elle est fournie)
        if reference:
            pharmacy = self.context['request'].user
            qs = Procedure.objects.filter(pharmacy=pharmacy, reference=reference)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'reference': 'Une procédure avec cette référence existe déjà.'}
                )

        return data

    def validate_content(self, value):
        return sanitize_quill_html(value)



# ── CorrectiveAction ──────────────────────────────────────────────────────────

class CorrectiveActionSerializer(serializers.ModelSerializer):
    responsible = serializers.SerializerMethodField()

    class Meta:
        model = CorrectiveAction
        fields = ['id', 'description', 'responsible', 'due_date', 'completed_at', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_responsible(self, obj):
        return _collab_repr(obj.responsible)


# ── NonConformity — List (léger) ──────────────────────────────────────────────

class NonConformityListSerializer(serializers.ModelSerializer):
    procedure = serializers.SerializerMethodField()
    reported_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model = NonConformity
        fields = [
            'id', 'title', 'severity', 'status',
            'procedure', 'reported_by', 'assigned_to',
            'due_date', 'created_at',
        ]

    def get_procedure(self, obj):
        if obj.procedure is None:
            return None
        return {'id': obj.procedure.id, 'title': obj.procedure.title}

    def get_reported_by(self, obj):
        return _collab_repr(obj.reported_by)

    def get_assigned_to(self, obj):
        return _collab_repr(obj.assigned_to)


# ── NonConformity — Detail (complet) ─────────────────────────────────────────

class NonConformityDetailSerializer(NonConformityListSerializer):
    closed_by = serializers.SerializerMethodField()
    corrective_actions = CorrectiveActionSerializer(many=True, read_only=True)

    class Meta(NonConformityListSerializer.Meta):
        fields = NonConformityListSerializer.Meta.fields + [
            'description', 'closed_at', 'closed_by', 'corrective_actions',
        ]
        # S02/S07 : le statut d'une NC (dont la clôture) ne passe QUE par les
        # actions dédiées assign/close (gardées par CanCloseNonConformities).
        # Sans ce read_only, un PATCH direct fixait status='closed' + closed_at
        # en contournant la permission.
        read_only_fields = ['status', 'closed_at', 'created_at']

    def get_closed_by(self, obj):
        return _collab_repr(obj.closed_by)
