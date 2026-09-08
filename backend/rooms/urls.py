"""
URL patterns for the rooms API.
"""

from django.urls import path
from rooms.views import (
    CreateRoomView,
    JoinRoomView,
    RoomDetailView,
    TicketExchangeView,
)

urlpatterns = [
    path("", CreateRoomView.as_view(), name="create_room"),
    path("ticket/", TicketExchangeView.as_view(), name="ticket_exchange"),
    path("<str:room_code>/", RoomDetailView.as_view(), name="room_detail"),
    path("<str:room_code>/join/", JoinRoomView.as_view(), name="join_room"),
]
