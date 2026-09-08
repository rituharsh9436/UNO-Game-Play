-- atomic_draw_card.lua
-- Atomically pops a card from draw pile and adds it to the player's hand set
-- KEYS[1]: Meta Hash (uno:room:<CODE>:meta)
-- KEYS[2]: Draw Pile List (uno:room:<CODE>:draw_pile)
-- KEYS[3]: Player Hand Set (uno:room:<CODE>:hands:<PLAYER_ID>)
-- ARGV[1]: Player ID
-- ARGV[2]: Sliding TTL in seconds (e.g. 7200)

local current_player = redis.call('HGET', KEYS[1], 'current_player_id')
if current_player ~= ARGV[1] then
    return redis.error_reply("NOT_YOUR_TURN")
end

local card_id = redis.call('LPOP', KEYS[2])
if not card_id then
    return redis.error_reply("DRAW_PILE_EMPTY")
end

redis.call('SADD', KEYS[3], card_id)
local new_version = redis.call('HINCRBY', KEYS[1], 'version', 1)

local ttl = tonumber(ARGV[2]) or 7200
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
redis.call('EXPIRE', KEYS[3], ttl)

return {new_version, card_id}
