from datetime import date
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.billing.permissions import HasPaidAccess


def _notify_tasks(pharmacy_id):
    """Envoie un signal WebSocket à tous les collaborateurs de la pharmacie."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'tasks_pharmacy_{pharmacy_id}',
        {'type': 'task_update'}
    )

from apps.team.models import Collaborator
from .models import Task, TaskComment
from .serializers import TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer, TaskCommentSerializer
from apps.core.auth_helpers import get_collaborator_from_jwt as _get_collaborator


def _sort_tasks(tasks):
    return sorted(tasks, key=lambda t: (t.order, -t.created_at.timestamp()))


class TaskListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # BLOC 4 — 1 seul SELECT au lieu de 3 : partition en Python
        all_tasks = list(
            Task.objects.filter(pharmacy=request.user)
            .select_related('created_by', 'assigned_to')
            .annotate(comments_count=Count('comments'))
        )

        personal = _sort_tasks([
            t for t in all_tasks if t.created_by_id == collaborator.id and t.type == 'PERSONAL'
        ])
        assigned_to_me = _sort_tasks([
            t for t in all_tasks if t.assigned_to_id == collaborator.id
        ])
        assigned_by_me = _sort_tasks([
            t for t in all_tasks if t.created_by_id == collaborator.id and t.type == 'ASSIGNED'
        ])

        return Response({
            'personal_tasks': TaskSerializer(personal, many=True).data,
            'assigned_to_me': TaskSerializer(assigned_to_me, many=True).data,
            'assigned_by_me': TaskSerializer(assigned_by_me, many=True).data,
        })

    def post(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "Session collaborateur requise."},
                status=status.HTTP_403_FORBIDDEN
            )
        # Vérification permission can_assign_task si c'est une tâche assignée
        if request.data.get('assigned_to_id') and not collaborator.can_assign_task:
            return Response(
                {"detail": "Vous n'avez pas la permission d'assigner des tâches."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = TaskCreateSerializer(data=request.data, context={'request': request, 'creator': collaborator})
        if serializer.is_valid():
            task = serializer.save()
            max_order = Task.objects.filter(pharmacy=request.user).aggregate(Max('order'))['order__max']
            task.order = (max_order or 0) + 1
            task.save(update_fields=['order'])
            _notify_tasks(request.user.id)
            return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskDetailView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def _get_task(self, task_id, request):
        return get_object_or_404(Task, id=task_id, pharmacy=request.user)

    def get(self, request, task_id):
        task = self._get_task(task_id, request)
        return Response(TaskSerializer(task).data)

    def patch(self, request, task_id):
        task = self._get_task(task_id, request)
        collaborator = _get_collaborator(request)
        if collaborator is None or (
            task.created_by_id != collaborator.id and task.assigned_to_id != collaborator.id
        ):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        serializer = TaskUpdateSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            task.refresh_from_db()
            _notify_tasks(request.user.id)
            return Response(TaskSerializer(task).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, task_id):
        task = self._get_task(task_id, request)
        collaborator = _get_collaborator(request)
        if collaborator is None or task.created_by_id != collaborator.id:
            return Response({"detail": "Seul le créateur peut supprimer cette tâche."}, status=status.HTTP_403_FORBIDDEN)
        task.delete()
        _notify_tasks(request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _check_involved(collaborator, task):
    """Retourne True si le collaborateur est créateur ou assigné à la tâche."""
    if collaborator is None:
        return False
    return task.created_by_id == collaborator.id or task.assigned_to_id == collaborator.id


class TaskStartView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        collaborator = _get_collaborator(request)
        if not _check_involved(collaborator, task):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        if task.status != 'TODO':
            return Response(
                {"detail": "Seules les tâches 'À faire' peuvent être démarrées."},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'IN_PROGRESS'
        task.started_at = timezone.now()
        task.save(update_fields=['status', 'started_at', 'updated_at'])
        _notify_tasks(request.user.id)
        return Response(TaskSerializer(task).data)


class TaskCompleteView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        collaborator = _get_collaborator(request)
        if not _check_involved(collaborator, task):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        if task.status == 'DONE':
            return Response({"detail": "Tâche déjà terminée."}, status=status.HTTP_400_BAD_REQUEST)
        task.status = 'DONE'
        task.completed_at = timezone.now()
        # Si le créateur lui-même termine la tâche, pas besoin de notification
        if task.created_by_id == collaborator.id:
            task.is_completion_seen = True
        task.save(update_fields=['status', 'completed_at', 'is_completion_seen', 'updated_at'])
        _notify_tasks(request.user.id)
        return Response(TaskSerializer(task).data)


class TaskReopenView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        collaborator = _get_collaborator(request)
        if not _check_involved(collaborator, task):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        if task.status != 'DONE':
            return Response(
                {"detail": "Seules les tâches terminées peuvent être réouvertes."},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'TODO'
        task.started_at = None
        task.completed_at = None
        task.is_completion_seen = False
        task.save(update_fields=['status', 'started_at', 'completed_at', 'is_completion_seen', 'updated_at'])
        _notify_tasks(request.user.id)
        return Response(TaskSerializer(task).data)


class TaskUnseenCountView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response({"unseen_count": 0})
        count = Task.objects.filter(
            pharmacy=request.user,
            created_by=collaborator,
            type='ASSIGNED',
            status='DONE',
            is_completion_seen=False
        ).count()
        return Response({"unseen_count": count})


class TaskMarkSeenView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant."},
                status=status.HTTP_400_BAD_REQUEST
            )
        Task.objects.filter(
            pharmacy=request.user,
            created_by=collaborator,
            type='ASSIGNED',
            status='DONE',
            is_completion_seen=False
        ).update(is_completion_seen=True)
        return Response({"detail": "Marqué comme vu."})


class TaskCommentListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        comments = task.comments.select_related('author')
        return Response(TaskCommentSerializer(comments, many=True).data)

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response({"detail": "Session collaborateur requise."}, status=status.HTTP_403_FORBIDDEN)
        content = request.data.get('content', '').strip()
        if not content:
            return Response({"detail": "Le commentaire ne peut pas être vide."}, status=status.HTTP_400_BAD_REQUEST)
        comment = TaskComment.objects.create(task=task, author=collaborator, content=content)
        _notify_tasks(request.user.id)
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class TaskReorderView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request):
        task_ids = request.data.get('task_ids', [])
        for i, task_id in enumerate(task_ids):
            Task.objects.filter(id=task_id, pharmacy=request.user).update(order=i)
        return Response({"detail": "Ordre mis à jour."})
