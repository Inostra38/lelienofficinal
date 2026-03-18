from rest_framework import serializers
from .models import Procedure, ProcedureAttachment, ProcedureImage, NonConformity, CorrectiveAction, ProcedureGroup, ProcedureVersion
from apps.team.models import Collaborator


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collab_repr(collab):
    """Retourne un dict {id, full_name} ou None."""
    if collab is None:
        return None
    return {'id': collab.id, 'full_name': f"{collab.first_name} {collab.last_name}"}


def _collab_list_repr(collabs):
    """Retourne une liste de dicts {id, full_name}."""
    return [{'id': c.id, 'full_name': f"{c.first_name} {c.last_name}"} for c in collabs.all()]


# ── Attachments & Images ──────────────────────────────────────────────────────

class ProcedureAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureAttachment
        fields = ['id', 'filename', 'file', 'uploaded_at']
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
        fields = ['id', 'version_number', 'change_summary', 'created_by', 'created_at']

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)


# ── ProcedureGroup ────────────────────────────────────────────────────────────

class ProcedureGroupSerializer(serializers.ModelSerializer):
    procedure_count = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = ProcedureGroup
        fields = ['id', 'name', 'description', 'color', 'procedure_count', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_procedure_count(self, obj):
        return obj.procedures.filter(parent=None).count()

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)


# ── Procedure — List (léger) ──────────────────────────────────────────────────

class ProcedureListSerializer(serializers.ModelSerializer):
    pilots = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    group = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'is_group', 'category', 'status',
            'version', 'position', 'parent', 'group', 'pilots', 'updated_at',
        ]

    def get_pilots(self, obj):
        return _collab_list_repr(obj.pilots)


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
    created_by = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Procedure.objects.all(),
        allow_null=True,
        required=False,
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=ProcedureGroup.objects.all(),
        allow_null=True,
        required=False,
    )
    attachments = ProcedureAttachmentSerializer(many=True, read_only=True)
    images = ProcedureImageSerializer(many=True, read_only=True)
    history = ProcedureVersionSerializer(many=True, read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'is_group', 'category', 'status',
            'version', 'position', 'parent', 'group', 'pilots', 'pilot_ids', 'updated_at',
            'content', 'file', 'created_by', 'created_at',
            'attachments', 'images', 'history', 'children',
        ]
        validators = []  # Gestion manuelle pour référence optionnelle (groupes)

    def get_pilots(self, obj):
        return _collab_list_repr(obj.pilots)

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)

    def get_children(self, obj):
        qs = obj.children.order_by('position').prefetch_related('pilots')
        return ProcedureListSerializer(qs, many=True, context=self.context).data

    def create(self, validated_data):
        pilots = validated_data.pop('pilots', [])
        instance = super().create(validated_data)
        instance.pilots.set(pilots)
        return instance

    def update(self, instance, validated_data):
        pilots = validated_data.pop('pilots', None)
        instance = super().update(instance, validated_data)
        if pilots is not None:
            instance.pilots.set(pilots)
        return instance

    def validate(self, data):
        is_group = data.get('is_group', getattr(self.instance, 'is_group', False))
        reference = data.get('reference', getattr(self.instance, 'reference', None))

        # Référence obligatoire pour les procédures standard
        if not is_group and not reference:
            raise serializers.ValidationError(
                {'reference': 'La référence est obligatoire pour une procédure standard.'}
            )

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

        parent = data.get('parent', getattr(self.instance, 'parent', None))
        instance = self.instance

        if parent is None:
            return data

        # Anti-cycle : le parent ne doit pas être un descendant de l'instance
        if instance is not None:
            node = parent
            while node is not None:
                if node.id == instance.id:
                    raise serializers.ValidationError(
                        "Le parent ne peut pas être un descendant de cette procédure (cycle)."
                    )
                node = node.parent

        # Vérification profondeur : parent.get_depth() + 1 <= 2
        if parent.get_depth() + 1 > 2:
            raise serializers.ValidationError(
                "La profondeur maximale de l'arborescence est de 3 niveaux."
            )

        return data


# ── Procedure — Tree (récursif) ───────────────────────────────────────────────

class ProcedureTreeSerializer(serializers.ModelSerializer):
    pilots = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ['id', 'title', 'reference', 'is_group', 'category', 'status', 'version', 'position', 'group', 'pilots', 'children']

    def get_pilots(self, obj):
        return _collab_list_repr(obj.pilots)

    def get_children(self, obj):
        qs = obj.children.order_by('position').prefetch_related('pilots')
        return ProcedureTreeSerializer(qs, many=True, context=self.context).data


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

    def get_closed_by(self, obj):
        return _collab_repr(obj.closed_by)
