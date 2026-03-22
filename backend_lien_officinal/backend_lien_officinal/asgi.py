"""
ASGI config — Le Lien Officinal
HTTP : Django REST Framework
WebSocket : Django Channels (messagerie temps réel)
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_lien_officinal.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.messaging.middleware import JWTAuthMiddleware
from apps.messaging.routing import websocket_urlpatterns as messaging_ws
from apps.tasks.routing import websocket_urlpatterns as tasks_ws
from apps.quality.routing import websocket_urlpatterns as quality_ws

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(messaging_ws + tasks_ws + quality_ws)
    ),
})
