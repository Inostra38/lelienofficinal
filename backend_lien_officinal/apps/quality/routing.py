from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/quality/ai/$', consumers.QualityAIConsumer.as_asgi()),
]
