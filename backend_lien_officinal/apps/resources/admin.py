from django.contrib import admin
from .models import Category, Link

class LinkInline(admin.TabularInline):
    model = Link
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre', 'icon_slug')
    list_editable = ('ordre',)
    inlines = [LinkInline] # Permet d'ajouter des liens directement dans la catégorie

@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ('titre', 'category', 'partner', 'url')
    list_filter = ('category', 'partner')
    search_fields = ('titre', 'url')