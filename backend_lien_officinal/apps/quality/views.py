from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Procedure, ProcedureAttachment, ProcedureImage, NonConformity, CorrectiveAction
from .serializers import (
    ProcedureListSerializer, ProcedureDetailSerializer, ProcedureTreeSerializer,
    ProcedureAttachmentSerializer, ProcedureImageSerializer,
    NonConformityListSerializer, NonConformityDetailSerializer,
    CorrectiveActionSerializer,
)
from .permissions import (
    IsPharmacyTitulaire, CanManageProcedures, CanPublishProcedures,
    CanCloseNonConformities, IsProcedurePilot, _get_collaborator,
)


# ── Procedure ─────────────────────────────────────────────────────────────────

class ProcedureViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Procedure.objects
            .filter(pharmacy=self.request.user)
            .select_related('pilot', 'created_by', 'parent')
            .prefetch_related('attachments', 'images')
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ProcedureListSerializer
        if self.action == 'tree':
            return ProcedureTreeSerializer
        return ProcedureDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated(), (CanManageProcedures | IsProcedurePilot)()]
        if self.action == 'destroy':
            return [IsAuthenticated(), CanManageProcedures()]
        if self.action == 'publish':
            return [IsAuthenticated(), CanPublishProcedures()]
        if self.action == 'archive':
            return [IsAuthenticated(), IsPharmacyTitulaire()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        collaborator = _get_collaborator(self.request, self.request.user)
        serializer.save(pharmacy=self.request.user, created_by=collaborator)

    # ── Actions custom ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def tree(self, request):
        roots = (
            self.get_queryset()
            .filter(parent=None)
            .order_by('position')
            .prefetch_related('children__pilot', 'children__children__pilot')
        )
        serializer = ProcedureTreeSerializer(roots, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        procedure = self.get_object()
        if procedure.status != Procedure.Status.DRAFT:
            return Response(
                {'detail': 'Seul un brouillon peut être publié.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Incrémente la version si la procédure a déjà été publiée (version > 1)
        if procedure.version > 1:
            procedure.version += 1
        procedure.status = Procedure.Status.ACTIVE
        procedure.save(update_fields=['status', 'version'])
        return Response(ProcedureDetailSerializer(procedure, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        procedure = self.get_object()
        procedure.status = Procedure.Status.ARCHIVED
        procedure.save(update_fields=['status'])
        return Response(ProcedureDetailSerializer(procedure, context={'request': request}).data)

    @action(detail=False, methods=['patch'])
    def reorder(self, request):
        items = request.data
        if not isinstance(items, list):
            return Response({'detail': 'Liste attendue.'}, status=status.HTTP_400_BAD_REQUEST)

        pharmacy = request.user
        ids = [item['id'] for item in items]
        procedures = {p.id: p for p in Procedure.objects.filter(id__in=ids, pharmacy=pharmacy)}

        if len(procedures) != len(ids):
            return Response(
                {'detail': 'Une ou plusieurs procédures sont introuvables ou non autorisées.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        for item in items:
            parent_id = item.get('parent_id')
            if parent_id is not None:
                try:
                    parent = Procedure.objects.get(id=parent_id, pharmacy=pharmacy)
                except Procedure.DoesNotExist:
                    return Response(
                        {'detail': f"parent_id={parent_id} introuvable."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if parent.get_depth() + 1 > 2:
                    return Response(
                        {'detail': f"Profondeur maximale dépassée pour la procédure {item['id']}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        with transaction.atomic():
            for item in items:
                p = procedures[item['id']]
                p.parent_id = item.get('parent_id')
                p.position = item.get('position', 0)
                p.save(update_fields=['parent_id', 'position'])

        return Response({'status': 'ok', 'updated': len(items)})

    @action(detail=True, methods=['post'], url_path='images')
    def upload_image(self, request, pk=None):
        procedure = self.get_object()
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'detail': 'Champ image manquant.'}, status=status.HTTP_400_BAD_REQUEST)
        img = ProcedureImage.objects.create(procedure=procedure, image=image_file)
        return Response(
            ProcedureImageSerializer(img, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'], url_path='attachments')
    def attachments(self, request, pk=None):
        procedure = self.get_object()
        if request.method == 'GET':
            qs = procedure.attachments.all()
            return Response(ProcedureAttachmentSerializer(qs, many=True).data)
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Champ file manquant.'}, status=status.HTTP_400_BAD_REQUEST)
        filename = request.data.get('filename', '') or file.name
        attachment = ProcedureAttachment.objects.create(
            procedure=procedure, file=file, filename=filename,
        )
        return Response(
            ProcedureAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )


# ── ProcedureAttachment (suppression seule) ───────────────────────────────────

class ProcedureAttachmentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProcedureAttachmentSerializer

    def get_queryset(self):
        return ProcedureAttachment.objects.filter(procedure__pharmacy=self.request.user)

    def destroy(self, request, *args, **kwargs):
        attachment = self.get_object()
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── NonConformity ─────────────────────────────────────────────────────────────

class NonConformityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            NonConformity.objects
            .filter(pharmacy=self.request.user)
            .select_related('procedure', 'reported_by', 'assigned_to', 'closed_by')
            .prefetch_related('corrective_actions')
        )
        status_param = self.request.query_params.get('status')
        severity_param = self.request.query_params.get('severity')
        assigned_param = self.request.query_params.get('assigned_to')
        if status_param:
            qs = qs.filter(status=status_param)
        if severity_param:
            qs = qs.filter(severity=severity_param)
        if assigned_param:
            qs = qs.filter(assigned_to_id=assigned_param)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return NonConformityListSerializer
        return NonConformityDetailSerializer

    def perform_create(self, serializer):
        collaborator = _get_collaborator(self.request, self.request.user)
        serializer.save(pharmacy=self.request.user, reported_by=collaborator)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        if not CanManageProcedures().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        nc = self.get_object()
        collab_id = request.data.get('assigned_to')
        if not collab_id:
            return Response({'detail': 'assigned_to requis.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.team.models import Collaborator
        try:
            collab = Collaborator.objects.get(id=collab_id, pharmacy=request.user, is_active=True)
        except Collaborator.DoesNotExist:
            return Response({'detail': 'Collaborateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        nc.assigned_to = collab
        if nc.status == NonConformity.Status.OPEN:
            nc.status = NonConformity.Status.IN_PROGRESS
        nc.save(update_fields=['assigned_to', 'status'])
        return Response(NonConformityDetailSerializer(nc).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        if not CanCloseNonConformities().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        nc = self.get_object()
        if nc.status != NonConformity.Status.IN_PROGRESS:
            return Response(
                {'detail': 'Seule une NC en cours peut être clôturée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        collaborator = _get_collaborator(request, request.user)
        resolution = request.data.get('resolution', '').strip()
        if resolution:
            CorrectiveAction.objects.create(
                nonconformity=nc,
                description=resolution,
                responsible=collaborator,
                completed_at=timezone.now(),
            )
        nc.closed_at = timezone.now()
        nc.closed_by = collaborator
        nc.status = NonConformity.Status.CLOSED
        nc.save(update_fields=['closed_at', 'closed_by', 'status'])
        return Response(NonConformityDetailSerializer(nc).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        if not IsPharmacyTitulaire().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        nc = self.get_object()
        if nc.status != NonConformity.Status.CLOSED:
            return Response(
                {'detail': 'Seule une NC clôturée peut être réouverte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        nc.status = NonConformity.Status.OPEN
        nc.closed_at = None
        nc.closed_by = None
        nc.save(update_fields=['status', 'closed_at', 'closed_by'])
        return Response(NonConformityDetailSerializer(nc).data)


# ── CorrectiveAction ──────────────────────────────────────────────────────────

class CorrectiveActionViewSet(
    viewsets.mixins.CreateModelMixin,
    viewsets.mixins.RetrieveModelMixin,
    viewsets.mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = CorrectiveActionSerializer

    def get_queryset(self):
        return CorrectiveAction.objects.filter(
            nonconformity__pharmacy=self.request.user
        ).select_related('responsible', 'nonconformity')

    def perform_create(self, serializer):
        nc_id = self.request.data.get('nonconformity')
        try:
            nc = NonConformity.objects.get(id=nc_id, pharmacy=self.request.user)
        except NonConformity.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Non-conformité introuvable ou non autorisée.')
        serializer.save(nonconformity=nc)
