"""
Security, Anti-Abuse, and Anti-DDoS Throttling Module.
Complies with docs.md Section 12.2.
"""

import time
from typing import Optional
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle


def get_client_ip(request: Request) -> str:
    """Extract real client IP considering NGINX / Cloudflare reverse proxy headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip.strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


class RoomCreationRateThrottle(BaseThrottle):
    """
    Strict rate-limiting: Caps room creation to 5 rooms per IP per hour (§12.2).
    """

    MAX_ROOMS_PER_HOUR = 5
    WINDOW_SECONDS = 3600

    def allow_request(self, request: Request, view: Optional[object]) -> bool:
        if request.method != "POST":
            return True

        ip = get_client_ip(request)
        cache_key = f"throttle:create_room:{ip}"
        creations = cache.get(cache_key, 0)

        if creations >= self.MAX_ROOMS_PER_HOUR:
            raise Throttled(
                detail="Room creation rate limit exceeded. Maximum 5 rooms per IP per hour permitted.",
                code="ROOM_CREATION_LIMIT_EXCEEDED",
            )

        # Increment count
        if creations == 0:
            cache.set(cache_key, 1, timeout=self.WINDOW_SECONDS)
        else:
            try:
                cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, creations + 1, timeout=self.WINDOW_SECONDS)

        return True


class RoomLookupRateThrottle(BaseThrottle):
    """
    Room lookup backoff: More than 10 failed join attempts per minute triggers
    a 15-minute temporary IP block (§12.2).
    """

    MAX_FAILED_ATTEMPTS = 10
    ATTEMPT_WINDOW_SECONDS = 60
    BLOCK_DURATION_SECONDS = 900  # 15 minutes

    @classmethod
    def check_is_blocked(cls, request: Request) -> bool:
        ip = get_client_ip(request)
        block_key = f"block:lookup_ip:{ip}"
        if cache.get(block_key):
            return True
        return False

    @classmethod
    def record_failed_attempt(cls, request: Request) -> None:
        ip = get_client_ip(request)
        block_key = f"block:lookup_ip:{ip}"
        count_key = f"attempts:lookup_failed:{ip}"

        failed_count = cache.get(count_key, 0) + 1
        cache.set(count_key, failed_count, timeout=cls.ATTEMPT_WINDOW_SECONDS)

        if failed_count >= cls.MAX_FAILED_ATTEMPTS:
            # Block IP for 15 minutes
            cache.set(block_key, True, timeout=cls.BLOCK_DURATION_SECONDS)

    def allow_request(self, request: Request, view: Optional[object]) -> bool:
        if self.check_is_blocked(request):
            raise Throttled(
                detail="IP address temporarily blocked due to repeated failed room lookup attempts (15 min cooldown).",
                code="IP_TEMPORARILY_BLOCKED",
            )
        return True
