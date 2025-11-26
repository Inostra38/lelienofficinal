# apps/partners/admin.py
from django.contrib import admin
from .models import Partner

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('nom', 'email_contact', 'is_active', 'inactivity_ad_active', 'inactivity_ad_priority')
    list_filter = ('is_active', 'inactivity_ad_active')
    search_fields = ('nom',)
    
    fieldsets = (
        ('Informations Générales', {
            'fields': ('nom', 'logo', 'site_web', 'email_contact', 'is_active')
        }),
        ('📺 Publicité Inactivité', {
            'fields': (
                'inactivity_ad_image', 
                'inactivity_ad_link', 
                'inactivity_ad_active', 
                'inactivity_ad_priority'
            ),
            'classes': ('collapse',),
            'description': 'Configurez la publicité qui s\'affiche après 30s d\'inactivité'
        }),
    )