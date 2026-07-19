from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.billing'
    label = 'billing'
    verbose_name = 'Facturation'

    def ready(self):
        # Crée l'abonnement d'essai à la naissance de toute pharmacie.
        from apps.billing import signals  # noqa: F401
