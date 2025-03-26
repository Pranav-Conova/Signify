from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path('ws/video/', consumers.VideoConsumer.as_asgi()),
]
