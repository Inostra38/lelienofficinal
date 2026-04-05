from django.contrib import admin
from .models import AdminUser, AdminAuditLog

admin.site.register(AdminUser)


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'admin', 'ip_address', 'detail')
    list_filter = ('action', 'admin')
    search_fields = ('detail', 'admin__email')
    readonly_fields = ('admin', 'action', 'detail', 'ip_address', 'created_at')
    ordering = ('-created_at',)
