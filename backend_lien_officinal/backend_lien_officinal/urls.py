# backend_lien_officinal/urls.py
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, include, re_path
from django.conf import settings
from apps.core.views import health_check, CookiePharmacyLoginView, CookieTokenRefreshView
from apps.core.views_media import serve_protected_media


def _spa_fallback(request):
    """
    Catch-all SPA : redirige vers /static/index.html servi par WhiteNoise.
    """
    return HttpResponseRedirect('/static/index.html')


urlpatterns = []

# Interface Django admin : uniquement en dev (en prod, utiliser l'admin SaaS Angular)
if settings.DEBUG:
    urlpatterns += [path('admin/', admin.site.urls)]

urlpatterns += [

    # Monitoring
    path('api/health/', health_check, name='health_check'),

    # Fichiers media protégés par JWT (avant la route static Django)
    path('media/<path:path>', serve_protected_media, name='protected_media'),

    # API Routes
    path('api/', include('apps.core.urls')),
    path('api/', include('apps.resources.urls')),
    path('api/', include('apps.team.urls')),
    path('api/', include('apps.partners.urls')),
    path('api/', include('apps.messaging.urls')),
    path('api/', include('apps.tasks.urls')),
    path('api/', include('apps.planning.urls')),
    path('api/quality/', include('apps.quality.urls')),
    path('api/admin/', include('apps.admin_panel.urls')),

    # Auth
    path('api/token/', CookiePharmacyLoginView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
]

# Catch-all SPA : en prod (DEBUG=False), toutes les routes non-API servent index.html
# En dev/test (DEBUG=True), pas de catch-all pour ne pas casser les 404 des tests
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^(?!api/|media/|admin/|static/).*$', _spa_fallback),
    ]