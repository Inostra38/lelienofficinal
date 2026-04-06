# backend_lien_officinal/urls.py
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include, re_path
from django.conf import settings
from apps.core.views import health_check, CookiePharmacyLoginView, CookieTokenRefreshView
from apps.core.views_media import serve_protected_media

# Charger index.html une seule fois au démarrage (perf)
_index_html = None


def _spa_fallback(request):
    """
    Catch-all SPA : sert le index.html Angular pour que le routing client fonctionne.
    """
    global _index_html
    if _index_html is None:
        import os
        import glob
        candidates = [
            str(settings.STATIC_ROOT / 'index.html'),
            str(settings.BASE_DIR.parent / 'frontend-lien-officinal' / 'dist' / 'frontend-lien-officinal' / 'browser' / 'index.html'),
        ]
        # Debug : chercher index.html dans staticfiles récursivement
        static_root = str(settings.STATIC_ROOT)
        found_files = glob.glob(os.path.join(static_root, '**/index*'), recursive=True)

        for candidate in candidates:
            if os.path.isfile(candidate):
                with open(candidate, 'r') as f:
                    _index_html = f.read()
                break

        if _index_html is None:
            # Debug : check si le build Angular existe
            angular_dist = str(settings.BASE_DIR.parent / 'frontend-lien-officinal' / 'dist' / 'frontend-lien-officinal' / 'browser')
            angular_parent = str(settings.BASE_DIR.parent / 'frontend-lien-officinal')
            app_root = str(settings.BASE_DIR.parent)
            debug_info = (
                f"<h1>Application not found</h1>"
                f"<pre>STATIC_ROOT: {settings.STATIC_ROOT}\n"
                f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}\n"
                f"Angular dist: {angular_dist}\n"
                f"Angular dist exists: {os.path.isdir(angular_dist)}\n"
                f"frontend-lien-officinal exists: {os.path.isdir(angular_parent)}\n"
                f"Files in /app (first 20): {os.listdir(app_root)[:20] if os.path.isdir(app_root) else 'NOT FOUND'}\n"
                f"Files in frontend (first 10): {os.listdir(angular_parent)[:10] if os.path.isdir(angular_parent) else 'NOT FOUND'}\n"
                f"Files in STATIC_ROOT (first 20): {os.listdir(static_root)[:20] if os.path.isdir(static_root) else 'NOT FOUND'}</pre>"
            )
            _index_html = debug_info
    return HttpResponse(_index_html, content_type='text/html')


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