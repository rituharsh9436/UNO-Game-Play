"""
Redis Lua Script Manager for Linearizable Atomic Mutations.
Compliant with docs.md Section 8.2.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import redis

LUA_DIR = Path(__file__).resolve().parent / "lua"


class RedisLuaManager:
    """
    Manages loading, SHA caching, and executing atomic Lua scripts in Redis.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self.redis = redis_client
        self._sha_cache: Dict[str, str] = {}
        self._scripts: Dict[str, str] = {}
        self._load_local_scripts()

    def _load_local_scripts(self) -> None:
        """Read all .lua files in the engine/lua directory."""
        if not LUA_DIR.exists():
            return
        for file in LUA_DIR.glob("*.lua"):
            with open(file, "r", encoding="utf-8") as f:
                self._scripts[file.stem] = f.read()

    def register_scripts(self, client: Optional[redis.Redis] = None) -> None:
        """Register script SHAs with the connected Redis instance."""
        target = client or self.redis
        if not target:
            return
        for name, script_code in self._scripts.items():
            sha = target.script_load(script_code)
            self._sha_cache[name] = sha

    def execute_script(
        self,
        script_name: str,
        keys: List[str],
        args: List[Any],
        client: Optional[redis.Redis] = None,
    ) -> Any:
        """Execute a registered script using EVALSHA with fallback to EVAL."""
        target = client or self.redis
        if not target:
            raise RuntimeError("No Redis client provided for Lua script execution.")

        sha = self._sha_cache.get(script_name)
        if not sha:
            script_code = self._scripts.get(script_name)
            if not script_code:
                raise FileNotFoundError(f"Lua script '{script_name}' not found.")
            sha = target.script_load(script_code)
            self._sha_cache[script_name] = sha

        try:
            return target.evalsha(sha, len(keys), *keys, *args)
        except redis.exceptions.NoScriptError:
            script_code = self._scripts[script_name]
            sha = target.script_load(script_code)
            self._sha_cache[script_name] = sha
            return target.evalsha(sha, len(keys), *keys, *args)

    def get_script_content(self, script_name: str) -> str:
        """Retrieve the raw content of a script."""
        if script_name not in self._scripts:
            raise FileNotFoundError(f"Lua script '{script_name}' not found.")
        return self._scripts[script_name]
