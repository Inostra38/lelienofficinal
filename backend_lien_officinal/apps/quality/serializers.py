from rest_framework import serializers
from .models import Procedure, ProcedureAttachment, ProcedureImage, NonConformity, CorrectiveAction
from apps.team.models import Collaborator


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collab_repr(collab):
    """Retourne un dict {id, full_name} ou None."""
    if collab is None:
        return None
    return {'id': collab.id, 'full_name': f"{collab.first_name} {collab.last_name}"}


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


# ── Procedure — List (léger) ──────────────────────────────────────────────────

class ProcedureListSerializer(serializers.ModelSerializer):
    pilot = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'category', 'status',
            'version', 'position', 'parent', 'pilot', 'updated_at',
        ]

    def get_pilot(self, obj):
        return _collab_repr(obj.pilot)


# ── Procedure — Detail (complet) ─────────────────────────────────────────────

class ProcedureDetailSerializer(serializers.ModelSerializer):
    pilot = serializers.SerializerMethodField()
    pilot_id = serializers.PrimaryKeyRelatedField(
        source='pilot',
        queryset=Collaborator.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
    )
    created_by = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Procedure.objects.all(),
        allow_null=True,
        required=False,
    )
    attachments = ProcedureAttachmentSerializer(many=True, read_only=True)
    images = ProcedureImageSerializer(many=True, read_only=True)

    class Meta:
        model = Procedure
        fields = [
            'id', 'title', 'reference', 'category', 'status',
            'version', 'position', 'parent', 'pilot', 'pilot_id', 'updated_at',
            'content', 'file', 'created_by', 'created_at',
            'attachments', 'images',
        ]

    def get_pilot(self, obj):
        return _collab_repr(obj.pilot)

    def get_created_by(self, obj):
        return _collab_repr(obj.created_by)

    def validate(self, data):
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
    pilot = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ['id', 'title', 'reference', 'category', 'status', 'version', 'position', 'pilot', 'children']

    def get_pilot(self, obj):
        return _collab_repr(obj.pilot)

    def get_children(self, obj):
        qs = obj.children.order_by('position').select_related('pilot')
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
