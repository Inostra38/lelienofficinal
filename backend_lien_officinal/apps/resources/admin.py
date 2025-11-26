from django.contrib import admin
from .models import Category, ResourceCard, ResourceItem, PharmacyPreference

class ResourceItemInline(admin.TabularInline):
    model = ResourceItem
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre', 'icon_slug')
    list_editable = ('ordre',)

@admin.register(ResourceCard)
class ResourceCardAdmin(admin.ModelAdmin):
    list_display = ('titre', 'category', 'type', 'owner_partner')
    list_filter = ('category', 'type')
    search_fields = ('titre',)
    inlines = [ResourceItemInline]  # Allows adding items directly within the card

@admin.register(ResourceItem)
class ResourceItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'card', 'type', 'url')
    list_filter = ('type', 'card__category')

@admin.register(PharmacyPreference)
class PharmacyPreferenceAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'card', 'is_favorite')