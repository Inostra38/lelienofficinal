from django.contrib import admin
from .models import SMSTemplate, SMSLog


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'pharmacy', 'created_at', 'updated_at')
    list_filter = ('pharmacy',)
    search_fields = ('title', 'pharmacy__nom_officine')


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'recipient_name', 'recipient_civilite', 'status', 'credits_used', 'sent_at')
    list_filter = ('pharmacy', 'status')
    readonly_fields = ('to_hash', 'sent_at')
    search_fields = ('recipient_name', 'pharmacy__nom_officine')
