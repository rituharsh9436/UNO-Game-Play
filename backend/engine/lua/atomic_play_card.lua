-- atomic_play_card.lua
-- Single-threaded linearizable card play mutation in Redis
-- KEYS[1]: Meta Hash (uno:room:<CODE>:meta)
-- KEYS[2]: Discard List (uno:room:<CODE>:discard_pile)
-- KEYS[3]: Player Hand Set (uno:room:<CODE>:hands:<PLAYER_ID>)
-- ARGV[1]: Player ID
-- ARGV[2]: Card ID
-- ARGV[3]: Next Player ID
-- ARGV[4]: New Active Color
-- ARGV[5]: Turn Deadline Milliseconds
-- ARGV[6]: Sliding TTL in seconds (e.g. 7200)

local current_player = redis.call('HGET', KEYS[1], 'current_player_id')
if current_player ~= ARGV[1] then
    return redis.error_reply("NOT_YOUR_TURN")
end

local has_card = redis.call('SISMEMBER', KEYS[3], ARGV[2])
if has_card == 0 then
    return redis.error_reply("CARD_NOT_IN_HAND")
end

-- Atomic Hand Removal & Discard Update
redis.call('SREM', KEYS[3], ARGV[2])
redis.call('RPUSH', KEYS[2], ARGV[2])
redis.call('HSET', KEYS[1], 
    'current_player_id', ARGV[3], 
    'active_color', ARGV[4], 
    'top_card_id', ARGV[2],
    'turn_deadline_ms', ARGV[5]
)
local new_version = redis.call('HINCRBY', KEYS[1], 'version', 1)

-- Maintain Sliding TTL (2 hours)
local ttl = tonumber(ARGV[6]) or 7200
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
redis.call('EXPIRE', KEYS[3], ttl)

return new_version
