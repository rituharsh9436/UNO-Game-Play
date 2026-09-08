"""
WebSocket routing for the rooms application.
"""

from django.urls import re_path
from rooms.consumers import UnoGameConsumer

websocket_urlpatterns = [
    re_path(r"^ws/rooms/(?P<room_code>[A-Za-z0-9]{6})/?$", UnoGameConsumer.as_asgi()),
]
