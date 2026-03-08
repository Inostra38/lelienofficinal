from datetime import date
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.team.models import Collaborator
from .models import Task
from .serializers import TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer


def _get_collaborator(request):
    collab_id = request.headers.get('X-Collaborator-Id')
    if not collab_id:
        return None
    try:
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except (Collaborator.DoesNotExist, ValueError):
        return None


PRIORITY_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}


def _sort_tasks(tasks):
    return sorted(tasks, key=lambda t: (
        PRIORITY_ORDER.get(t.priority, 99),
        t.due_date or date.max,
        t.created_at,
    ))


class TaskListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant."},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_qs = Task.objects.filter(pharmacy=request.user).select_related('created_by', 'assigned_to')

        personal = _sort_tasks(list(base_qs.filter(created_by=collaborator, type='PERSONAL')))
        assigned_to_me = _sort_tasks(list(base_qs.filter(assigned_to=collaborator)))
        assigned_by_me = _sort_tasks(list(base_qs.filter(created_by=collaborator, type='ASSIGNED')))

        return Response({
            'personal_tasks': TaskSerializer(personal, many=True).data,
            'assigned_to_me': TaskSerializer(assigned_to_me, many=True).data,
            'assigned_by_me': TaskSerializer(assigned_by_me, many=True).data,
        })

    def post(self, request):
        serializer = TaskCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            task = serializer.save()
            return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

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
            return Response(TaskSerializer(task).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, task_id):
        task = self._get_task(task_id, request)
        collaborator = _get_collaborator(request)
        if collaborator is None or (
            task.created_by_id != collaborator.id and task.assigned_to_id != collaborator.id
        ):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        if task.status != 'TODO':
            return Response(
                {"detail": "Seules les tâches 'À faire' peuvent être démarrées."},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'IN_PROGRESS'
        task.save(update_fields=['status', 'updated_at'])
        return Response(TaskSerializer(task).data)


class TaskCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        if task.status == 'DONE':
            return Response({"detail": "Tâche déjà terminée."}, status=status.HTTP_400_BAD_REQUEST)
        task.status = 'DONE'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at', 'updated_at'])
        return Response(TaskSerializer(task).data)


class TaskReopenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, pharmacy=request.user)
        if task.status != 'DONE':
            return Response(
                {"detail": "Seules les tâches terminées peuvent être réouvertes."},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'TODO'
        task.completed_at = None
        task.is_completion_seen = False
        task.save(update_fields=['status', 'completed_at', 'is_completion_seen', 'updated_at'])
        return Response(TaskSerializer(task).data)


class TaskUnseenCountView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
