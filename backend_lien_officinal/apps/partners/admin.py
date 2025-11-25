from django.contrib import admin
from .models import Partner

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('nom', 'email_contact', 'is_active')
    search_fields = ('nom',)