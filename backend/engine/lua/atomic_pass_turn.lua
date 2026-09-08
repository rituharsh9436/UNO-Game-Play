-- atomic_pass_turn.lua
-- Advance turn atomically in Redis
-- KEYS[1]: Meta Hash (uno:room:<CODE>:meta)
-- ARGV[1]: Current Player ID
-- ARGV[2]: Next Player ID
-- ARGV[3]: Next Turn Deadline Milliseconds
-- ARGV[4]: Sliding TTL

local current_player = redis.call('HGET', KEYS[1], 'current_player_id')
if current_player ~= ARGV[1] then
    return redis.error_reply("NOT_YOUR_TURN")
end

redis.call('HSET', KEYS[1], 'current_player_id', ARGV[2], 'turn_deadline_ms', ARGV[3])
local new_version = redis.call('HINCRBY', KEYS[1], 'version', 1)

local ttl = tonumber(ARGV[4]) or 7200
redis.call('EXPIRE', KEYS[1], ttl)

return new_version
