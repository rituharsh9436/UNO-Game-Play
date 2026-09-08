"""
Django Admin configurations for Room, RoomPlayer, and Match models.
"""

from django.contrib import admin
from rooms.models import Match, Room, RoomPlayer


class RoomPlayerInline(admin.TabularInline):
    model = RoomPlayer
    extra = 0
    readonly_fields = ("id", "session_token", "joined_at")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_code", "status", "player_count", "max_players", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("room_code",)
    inlines = [RoomPlayerInline]


@admin.register(RoomPlayer)
class RoomPlayerAdmin(admin.ModelAdmin):
    list_display = ("nickname", "room", "is_host", "is_ready", "connected", "seat_order", "joined_at")
    list_filter = ("is_host", "is_ready", "connected")
    search_fields = ("nickname", "session_token", "room__room_code")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "winner_player", "total_turns", "duration_seconds", "finished_at")
    list_filter = ("finished_at",)
    search_fields = ("room__room_code", "winner_player__nickname")
