from django.contrib import admin
from .models import Procedure, ProcedureAttachment, ProcedureImage, NonConformity, CorrectiveAction


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ('title', 'reference', 'category', 'status', 'version', 'pharmacy', 'pilot')
    list_filter = ('status', 'category', 'pharmacy')
    search_fields = ('title', 'reference')
    raw_id_fields = ('pilot', 'created_by', 'parent')


@admin.register(ProcedureAttachment)
class ProcedureAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'procedure', 'uploaded_at')


@admin.register(ProcedureImage)
class ProcedureImageAdmin(admin.ModelAdmin):
    list_display = ('procedure', 'uploaded_at')


@admin.register(NonConformity)
class NonConformityAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'status', 'reported_by', 'assigned_to', 'pharmacy')
    list_filter = ('status', 'severity', 'pharmacy')
    search_fields = ('title',)
    raw_id_fields = ('reported_by', 'assigned_to', 'closed_by', 'procedure')


@admin.register(CorrectiveAction)
class CorrectiveActionAdmin(admin.ModelAdmin):
    list_display = ('nonconformity', 'responsible', 'due_date', 'completed_at')
    raw_id_fields = ('nonconformity', 'responsible')
