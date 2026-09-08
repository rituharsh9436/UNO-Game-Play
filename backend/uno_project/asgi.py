"""
ASGI config for UNO Project.
Exposes the ASGI callable as a module-level variable named ``application``.
Supports both standard HTTP requests and asynchronous WebSockets via Django Channels.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uno_project.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
import rooms.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            URLRouter(rooms.routing.websocket_urlpatterns)
        ),
    }
)
