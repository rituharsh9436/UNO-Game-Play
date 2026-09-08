"""
Unit tests for Redis Lua script loading and validation.
Complies with docs.md Section 8.2.
"""

from engine.lua_manager import RedisLuaManager


class TestLuaManager:
    def test_scripts_loaded(self) -> None:
        manager = RedisLuaManager()
        assert "atomic_play_card" in manager._scripts
        assert "atomic_draw_card" in manager._scripts
        assert "atomic_pass_turn" in manager._scripts

    def test_play_card_script_structure(self) -> None:
        manager = RedisLuaManager()
        script = manager.get_script_content("atomic_play_card")
        assert "NOT_YOUR_TURN" in script
        assert "CARD_NOT_IN_HAND" in script
        assert "SREM" in script
        assert "RPUSH" in script
        assert "HINCRBY" in script
        assert "EXPIRE" in script

    def test_draw_card_script_structure(self) -> None:
        manager = RedisLuaManager()
        script = manager.get_script_content("atomic_draw_card")
        assert "NOT_YOUR_TURN" in script
        assert "DRAW_PILE_EMPTY" in script
        assert "LPOP" in script
        assert "SADD" in script

    def test_pass_turn_script_structure(self) -> None:
        manager = RedisLuaManager()
        script = manager.get_script_content("atomic_pass_turn")
        assert "NOT_YOUR_TURN" in script
        assert "HSET" in script
        assert "HINCRBY" in script
