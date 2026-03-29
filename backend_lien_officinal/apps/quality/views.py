from django.db import transaction
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Subquery, Value
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Procedure, ProcedureAttachment, ProcedureImage, NonConformity,
    CorrectiveAction, ProcedureGroup, ProcedureVersion, ProcedureCategory,
    ProcedureNotification, ProcedureReadLog,
)
from .serializers import (
    ProcedureGroupSerializer, ProcedureCategorySerializer,
    ProcedureListSerializer, ProcedureDetailSerializer,
    ProcedureAttachmentSerializer, ProcedureImageSerializer,
    NonConformityListSerializer, NonConformityDetailSerializer,
    CorrectiveActionSerializer,
)
from .permissions import (
    IsPharmacyTitulaire, CanManageProcedures, CanManageQuality, CanEditProcedure,
    CanPublishProcedures, CanCloseNonConformities, IsProcedurePilot, _get_collaborator,
)


# ── Procedure ─────────────────────────────────────────────────────────────────

class ProcedureViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            Procedure.objects
            .filter(pharmacy=self.request.user)
            .select_related('created_by', 'archived_by', 'group')
            .prefetch_related('pilots', 'categories', 'attachments', 'images')
        )
        # Filtre archivage uniquement sur la liste
        if self.action == 'list':
            if self.request.query_params.get('archived') == 'true':
                qs = qs.filter(status=Procedure.Status.ARCHIVED)
            else:
                qs = qs.exclude(status=Procedure.Status.ARCHIVED)

        # Annotation : dernière version publiée (sous-requête SQL, pas de N+1)
        last_pub_sq = (
            ProcedureVersion.objects
            .filter(procedure=OuterRef('pk'))
            .order_by('-version_number')
            .values('version_number')[:1]
        )
        qs = qs.annotate(last_published_version=Subquery(last_pub_sq))

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # Annotation is_unread : notification non lue pour le collaborateur courant
        collab_id = self.request.auth.get('collaborator_id') if self.request.auth else None
        if collab_id:
            qs = qs.annotate(
                is_unread=Exists(
                    ProcedureNotification.objects.filter(
                        procedure=OuterRef('pk'),
                        recipient_id=collab_id,
                        is_read=False,
                    )
                )
            )
        else:
            qs = qs.annotate(is_unread=Value(False, output_field=BooleanField()))

        group_param = self.request.query_params.get('group')
        if group_param == 'none':
            qs = qs.filter(group__isnull=True)
        elif group_param:
            qs = qs.filter(group__id=group_param)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ProcedureListSerializer
        return ProcedureDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), CanManageQuality()]
        if self.action in ('update', 'partial_update'):
            return [IsAuthenticated(), CanEditProcedure()]
        if self.action == 'destroy':
            return [IsAuthenticated(), CanManageProcedures()]
        if self.action == 'publish':
            return [IsAuthenticated(), CanPublishProcedures()]
        if self.action in ('archive', 'unarchive'):
            return [IsAuthenticated(), CanManageProcedures()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        collaborator = _get_collaborator(self.request, self.request.user)
        serializer.save(pharmacy=self.request.user, created_by=collaborator)

    def perform_update(self, serializer):
        # Si on modifie une procédure active, elle repasse automatiquement en brouillon
        instance = self.get_object()
        if instance.status == Procedure.Status.ACTIVE:
            serializer.save(status=Procedure.Status.DRAFT)
        else:
            serializer.save()

    # ── Actions custom ──────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        collaborator = _get_collaborator(request, request.user)
        change_summary = request.data.get('change_summary', '')

        with transaction.atomic():
            # select_for_update() verrouille la ligne — empêche deux publications simultanées
            procedure = Procedure.objects.select_for_update().get(pk=pk)

            if procedure.pharmacy != request.user:
                return Response(status=status.HTTP_404_NOT_FOUND)

            if procedure.status != Procedure.Status.DRAFT:
                return Response(
                    {'detail': 'Seul un brouillon peut être publié.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            published_version = procedure.version

            # Archiver la version actuelle
            ProcedureVersion.objects.create(
                procedure=procedure,
                version_number=published_version,
                content=procedure.content or "",
                change_summary=change_summary or (f"Publication initiale" if published_version == 1 else f"Mise à jour v{published_version}"),
                created_by=collaborator
            )

            # Mise à jour atomique : F() évite tout read-modify-write
            Procedure.objects.filter(pk=pk).update(
                status=Procedure.Status.ACTIVE,
                version=F('version') + 1,
            )
            procedure.refresh_from_db()

            # Notifier tous les collaborateurs actifs (sauf celui qui publie)
            from apps.team.models import Collaborator as CollaboratorModel
            all_collabs = CollaboratorModel.objects.filter(pharmacy=procedure.pharmacy, is_active=True)
            notif_bulk = [
                ProcedureNotification(
                    recipient=collab,
                    procedure=procedure,
                    version_number=published_version,
                )
                for collab in all_collabs
                if collab != collaborator
            ]
            ProcedureNotification.objects.bulk_create(notif_bulk)

        return Response(ProcedureDetailSerializer(procedure, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        procedure = self.get_object()
        collaborator = _get_collaborator(request, request.user)
        procedure.status = Procedure.Status.ARCHIVED
        procedure.archived_at = timezone.now()
        procedure.archived_by = collaborator
        procedure.save(update_fields=['status', 'archived_at', 'archived_by'])
        # Promouvoir les sous-procédures en racine
        procedure.children.update(parent=None)
        return Response(ProcedureDetailSerializer(procedure, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        collaborator = _get_collaborator(request, request.user)
        if not collaborator:
            return Response(status=status.HTTP_204_NO_CONTENT)
        ProcedureNotification.objects.filter(
            procedure_id=pk,
            recipient=collaborator,
            is_read=False,
        ).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='log-read')
    def log_read(self, request, pk=None):
        """POST /api/quality/procedures/{id}/log-read/ — enregistre une lecture complète (scroll ≥ 90 %)."""
        collaborator = _get_collaborator(request, request.user)
        if not collaborator:
            return Response(status=status.HTTP_204_NO_CONTENT)
        procedure = self.get_object()
        ProcedureReadLog.objects.create(
            procedure=procedure,
            collaborator=collaborator,
            version_number=procedure.version,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        procedure = self.get_object()
        procedure.status = Procedure.Status.DRAFT
        procedure.archived_at = None
        procedure.archived_by = None
        procedure.save(update_fields=['status', 'archived_at', 'archived_by'])
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

        with transaction.atomic():
            for item in items:
                p = procedures[item['id']]
                p.position = item.get('position', 0)
                fields = ['position']
                if 'group_id' in item:
                    p.group_id = item.get('group_id')
                    fields.append('group_id')
                if 'parent_id' in item:
                    p.parent_id = item.get('parent_id')
                    fields.append('parent_id')
                p.save(update_fields=fields)

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
        if file.size > 10 * 1024 * 1024:
            return Response(
                {'detail': 'Le fichier dépasse la limite de 10 Mo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        original_name = file.name
        filename = request.data.get('filename', '') or original_name
        ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
        file_type = 'image' if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp') else 'document'
        collaborator = _get_collaborator(request, request.user)
        attachment = ProcedureAttachment.objects.create(
            procedure=procedure,
            file=file,
            filename=filename,
            original_name=original_name,
            file_type=file_type,
            uploaded_by=collaborator,
        )
        return Response(
            ProcedureAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )


# ── ProcedureCategory ─────────────────────────────────────────────────────────

class ProcedureCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ProcedureCategorySerializer

    def get_queryset(self):
        return ProcedureCategory.objects.filter(pharmacy=self.request.user, is_active=True)

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanManageQuality()]

    def perform_create(self, serializer):
        collaborator = _get_collaborator(self.request, self.request.user)
        serializer.save(pharmacy=self.request.user, created_by=collaborator)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.archived_at = timezone.now()
        instance.save(update_fields=['is_active', 'archived_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── ProcedureGroup ────────────────────────────────────────────────────────────

class ProcedureGroupViewSet(viewsets.ModelViewSet):
    serializer_class = ProcedureGroupSerializer

    def get_queryset(self):
        return (
            ProcedureGroup.objects
            .filter(pharmacy=self.request.user, is_active=True)
            .annotate(procedure_count=Count('procedures', distinct=True))
            .order_by('order')
        )

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanManageQuality()]

    def perform_create(self, serializer):
        collaborator = _get_collaborator(self.request, self.request.user)
        serializer.save(pharmacy=self.request.user, created_by=collaborator)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.archived_at = timezone.now()
        instance.save(update_fields=['is_active', 'archived_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        ordered_ids = request.data.get('order', [])
        if not isinstance(ordered_ids, list):
            return Response({'detail': 'Clé "order" (liste) attendue.'}, status=status.HTTP_400_BAD_REQUEST)
        pharmacy = request.user
        groups = {g.id: g for g in ProcedureGroup.objects.filter(id__in=ordered_ids, pharmacy=pharmacy)}
        if len(groups) != len(ordered_ids):
            return Response({'detail': 'Un ou plusieurs groupes introuvables.'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for position, group_id in enumerate(ordered_ids):
                groups[group_id].order = position
                groups[group_id].save(update_fields=['order'])
        return Response({'status': 'ok'})


# ── ProcedureImage (suppression seule) ───────────────────────────────────────

class ProcedureImageViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProcedureImageSerializer

    def get_queryset(self):
        return ProcedureImage.objects.filter(procedure__pharmacy=self.request.user)

    def destroy(self, request, *args, **kwargs):
        image = self.get_object()
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


# ── ProcedureNotification ─────────────────────────────────────────────────────

class ProcedureNotificationViewSet(
    viewsets.mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def _get_collaborator(self):
        return _get_collaborator(self.request, self.request.user)

    def get_queryset(self):
        collaborator = self._get_collaborator()
        if not collaborator:
            return ProcedureNotification.objects.none()
        return (
            ProcedureNotification.objects
            .filter(recipient=collaborator, procedure__pharmacy=self.request.user)
            .select_related('procedure')
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        full_qs = self.get_queryset()
        unread_count = full_qs.filter(is_read=False).count()
        qs = list(full_qs[:50])
        data = [
            {
                'id': n.id,
                'procedure_id': n.procedure_id,
                'procedure_title': n.procedure.title,
                'version_number': n.version_number,
                'is_read': n.is_read,
                'created_at': n.created_at,
            }
            for n in qs
        ]
        return Response({'results': data, 'unread_count': unread_count})

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        notif_ids = request.data.get('ids', [])
        collaborator = self._get_collaborator()
        if not collaborator:
            return Response({'status': 'ok'})
        qs = ProcedureNotification.objects.filter(
            recipient=collaborator, procedure__pharmacy=request.user
        )
        if notif_ids:
            qs = qs.filter(id__in=notif_ids)
        qs.update(is_read=True)
        return Response({'status': 'ok'})
