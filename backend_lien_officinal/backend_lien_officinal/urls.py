# backend_lien_officinal/urls.py
import os
from django.contrib import admin
from django.http import HttpResponse, FileResponse, HttpResponseNotFound
from django.urls import path, include, re_path
from django.conf import settings
from apps.core.views import health_check, CookiePharmacyLoginView, CookieTokenRefreshView
from apps.core.views_media import serve_protected_media


def _spa_fallback(request):
    """
    Catch-all SPA : sert index.html pour que le routing Angular fonctionne.
    Cherche dans staticfiles/ (après collectstatic) ou dans le dist Angular.
    """
    candidates = [
        os.path.join(str(settings.STATIC_ROOT), 'index.html'),
        str(settings.BASE_DIR.parent / 'frontend-lien-officinal' / 'dist' / 'frontend-lien-officinal' / 'browser' / 'index.html'),
    ]
    for path_candidate in candidates:
        if os.path.isfile(path_candidate):
            return FileResponse(open(path_candidate, 'rb'), content_type='text/html')
    return HttpResponseNotFound('index.html not found')


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

# Catch-all SPA : en prod (DEBUG=False)
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^(?!api/|media/|admin/|static/).*$', _spa_fallback),
    ]
