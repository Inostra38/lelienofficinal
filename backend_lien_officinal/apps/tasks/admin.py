from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'status', 'priority', 'created_by', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority', 'type']
    search_fields = ['title', 'description']
