import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from processing.routing import websocket_urlpatterns
import django
from channels.sessions import SessionMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "video_processing.settings")
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
     "websocket": SessionMiddlewareStack(
        AuthMiddlewareStack(
            URLRouter(
            websocket_urlpatterns
        )
        )
    ),
})