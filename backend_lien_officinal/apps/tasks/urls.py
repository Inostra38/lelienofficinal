from django.urls import path
from . import views

urlpatterns = [
    path('tasks/unseen-count/', views.TaskUnseenCountView.as_view(), name='task-unseen-count'),
    path('tasks/mark-seen/', views.TaskMarkSeenView.as_view(), name='task-mark-seen'),
    path('tasks/', views.TaskListCreateView.as_view(), name='task-list-create'),
    path('tasks/<uuid:task_id>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('tasks/<uuid:task_id>/start/', views.TaskStartView.as_view(), name='task-start'),
    path('tasks/<uuid:task_id>/complete/', views.TaskCompleteView.as_view(), name='task-complete'),
    path('tasks/<uuid:task_id>/reopen/', views.TaskReopenView.as_view(), name='task-reopen'),
]
