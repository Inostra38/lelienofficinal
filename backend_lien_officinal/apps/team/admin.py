from django.contrib import admin
from django import forms
from .models import Collaborator

class CollaboratorForm(forms.ModelForm):
    """Formulaire personnalisé pour gérer le PIN."""
    pin_code = forms.CharField(
        label="Code PIN (4-6 chiffres)",
        widget=forms.PasswordInput,
        required=False,
        help_text="Laissez vide pour conserver le PIN actuel."
    )

    class Meta:
        model = Collaborator
        fields = '__all__'

    def save(self, commit=True):
        collaborator = super().save(commit=False)
        # Si un nouveau PIN est entré, on le hache
        pin = self.cleaned_data.get('pin_code')
        if pin:
            collaborator.set_pin(pin)
        if commit:
            collaborator.save()
        return collaborator

@admin.register(Collaborator)
class CollaboratorAdmin(admin.ModelAdmin):
    form = CollaboratorForm
    list_display = ('first_name', 'last_name', 'role', 'pharmacy', 'is_active')
    list_filter = ('pharmacy', 'role', 'is_active')
    search_fields = ('first_name', 'last_name', 'pharmacy__nom_officine')
    
    # On exclue le champ pin_hash de l'affichage direct pour éviter les erreurs
    exclude = ('pin_hash',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Rend le champ PIN obligatoire uniquement à la création (pas à l'édition)
        form.base_fields['pin_code'].required = (obj is None)
        return form