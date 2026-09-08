# Multiplayer UNO — Comprehensive System & Product Specification (v2.1)

---

## Document Control & Architecture Foreword

| Attribute | Details |
| :--- | :--- |
| **Project Title** | Real-Time Server-Authoritative Multiplayer UNO Web Platform |
| **Document Version** | 2.1.0 (Enterprise Architecture & Security Hardened Baseline) |
| **Status** | Approved for Development Baseline |
| **Primary Target** | Web (Desktop & Mobile Responsive Browsers) |
| **Security Classification**| Zero-Trust Public Web Application |
| **Repository Baseline** | `newdocs.md` (Supersedes `docs.md` and `newdocs.md v2.0`) |

---

# 1. Executive Summary & Product Vision

Multiplayer UNO is a low-latency, real-time web application allowing groups of 2 to 6 players to play standard and house-rule UNO seamlessly without requiring account registration. The platform balances high accessibility (guest-friendly instant room links, 6-character clean room codes) with enterprise-grade resilience (server-authoritative rule enforcement, cheat prevention, distributed state management, and disconnection self-healing).

### Core Product Tenets
1. **Frictionless Entry:** Zero-login onboarding. A player can create a room, click a shareable link or copy a 6-character alphanumeric code, invite friends, and be playing within 15 seconds.
2. **Absolute Server Authority:** The browser is strictly a render and input-capture client. Card legality, turn sequences, deck shuffles, draw actions, and win conditions are calculated exclusively on the server.
3. **Information Security:** Zero client-side leakage of opponents' cards or the draw pile sequence. WebSocket payloads are sanitized per recipient.
4. **Anti-Stall & Resilience:** Games cannot be held hostage by disconnected or AFK players. Server-side turn timers, distributed deadline timestamps, and automated bot takeovers ensure fluid gameplay.
5. **Horizontal Scalability:** Decoupled ASGI WebSocket consumers backed by a high-throughput Redis state-and-channel layer using atomic Lua scripts, with PostgreSQL retaining permanent records.

---

# 2. Senior PM & Security Architect Review: Rectifications

A critical audit of the preliminary plan (`docs.md`) and initial architecture revealed security vulnerabilities and operational failure modes. All items have been resolved in this specification:

### Comprehensive Audit & Rectification Matrix

```text
┌─────────────────────────────┬─────────────────────────────────────┬───────────────────────────────────────────┐
│ Preliminary Plan / Defect   │ Risk / Failure Mode Identified      │ Architectural Resolution (v2.1)           │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ 10-Digit Numeric Room Code  │ High cognitive load, prone to typos │ 6-Character Uppercase Alphanumeric        │
│ (e.g. 7391846251)           │ on voice/chat (e.g., Discord)       │ (e.g. "K7X9W2", omitting O, 0, I, 1)      │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Token in WSS Query String   │ Leaked via reverse proxy logs, WAF  │ Ephemeral Single-Use Ticket Exchange      │
│ (?token=<SESSION_TOKEN>)    │ access logs, and browser histories  │ (POST /api/rooms/ticket -> 30s ticket)    │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Distributed Mutex (Redlock) │ Lock acquisition overhead, clock    │ Atomic Redis Lua Scripts                  │
│ for Concurrency Control     │ drift, deadlocks on worker crash    │ (single-threaded, linearizable mutations) │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ In-Memory Turn Timers       │ Worker pod restart/crash kills      │ Distributed Timestamp Deadlines + Redis   │
│ (e.g. asyncio.sleep(25))    │ timers, permanently freezing game   │ Keyspace Expiry Notifications             │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Unprotected State-Sync      │ Malicious clients spam sync calls   │ Token-bucket rate limiting: max 1 sync    │
│ Event (DoS Amplification)   │ to saturate CPU & network bandwidth │ per 3 seconds per player; frame cap 16KB  │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Room Code Brute-Forcing &   │ Automated bots exhaust server memory│ IP-based rate limiting (5 rooms/hr/IP),   │
│ Memory Squatting Attack     │ by opening millions of idle rooms   │ idle room TTL (5 min), search backoff     │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Vague "Call UNO" Rule       │ Undefined timing window leads to    │ Formal "Call UNO" button + 3s "Catch UNO" │
│ Implementation              │ client race conditions & disputes   │ challenge window for opponents            │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Disconnect Policy Left as   │ Abandoned rooms clog servers; host  │ 45s grace period, dynamic host migration, │
│ "To Be Defined Later"       │ disconnect aborts room prematurely  │ and auto-surrender after grace timeout    │
├─────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────────────┤
│ Typo Contradiction in §41   │ Confuses engineering team on DB     │ PostgreSQL strictly designated as DB;     │
│ (mentions MongoDB once)     │ selection and ORM strategy          │ MongoDB references eliminated             │
└─────────────────────────────┴─────────────────────────────────────┴───────────────────────────────────────────┘
```

---

# 3. Target Technology Stack & Infrastructure Topology

```text
                                  INTERNET
                                     |
                          +----------v----------+
                          |   Cloudflare / Edge  |  - WAF Rate Limiting & TLS 1.3 Termination
                          |      DDoS Shield    |  - Geo-blocking & Bot Protection
                          +----------+----------+
                                     |
                          +----------v----------+
                          |   NGINX Ingress     |  - Max payload: 16KB
                          |   Reverse Proxy     |  - Anti-Slowloris (read_timeout: 60s)
                          +----+-----------+----+  - WebSocket Upgrade & Proxying
                               |           |
               HTTPS (REST)    |           |   WebSockets (WSS)
        (Session/Ticket API)   |           | (Gameplay & Live Presence)
                               |           |
                               v           v
                          +---------------------+
                          |   Application Pods  |
                          | (Django 5 + Daphne) |  - Stateless ASGI Workers
                          +----------+----------+
                                     |
                 +-------------------+-------------------+
                 |                                       |
                 v                                       v
      +----------------------+               +----------------------+
      |      Redis 7.x       |               |    PostgreSQL 16+    |
      | - Channel Layer Bus  |               | - Match History      |
      | - Active State Hashes|               | - Player Audit Logs  |
      | - Atomic Lua Scripts |               | - Room Metrics       |
      | - Ephemeral Tickets  |               | - PgBouncer Pooling  |
      | (volatile-lru, TTL)  |               +----------------------+
      +----------------------+
```

### 3.1 Frontend: Next.js 14+ (App Router, TypeScript)
- **Role:** High-performance, mobile-first responsive client.
- **Key Modules:**
  - `Context / Zustand`: Centralized WebSocket connection and state synchronization store.
  - `Framer Motion`: 60fps card play, card deal, and turn indicator transitions.
  - `Howler.js`: Cross-browser, zero-lag spatial sound effects (card deals, skip alerts, reverse swoosh, UNO shout, countdown chime).
  - `Tailwind CSS`: Fluid responsive grid adapting from 320px smartphones to 4K ultra-wide monitors.

### 3.2 Backend: Django 5.x + Django Channels 4.x + DRF
- **Role:** Server-authoritative game brain and API gateway.
- **Key Modules:**
  - `Django REST Framework (DRF)`: Room creation, code validation, token/ticket issuance, health checks.
  - `Django Channels + Daphne (ASGI)`: High-concurrency asynchronous WebSocket handling.
  - `Pure Python UNO Engine`: Zero external dependencies, pure isolated deterministic logic, enabling 100% unit-testable game loops.

### 3.3 Active State Store & Message Broker: Redis 7.x
- **Role:**
  1. **Channels Layer:** Cross-worker broadcast bus for WebSocket groups.
  2. **Active Game State Cache:** Room states serialized in Redis hashes with TTL, eliminating slow relational database queries on every sub-second card play.
  3. **Concurrency Control:** Atomic operations via single-threaded **Redis Lua Scripts** preventing race conditions without distributed deadlocks.
  4. **Distributed Timers:** Timestamp deadlines paired with Redis TTL keys (`SETEX`).
  5. **Ephemeral Tickets:** Single-use, 30-second ticket tokens for secure WebSocket authentication.

### 3.4 Persistent Database: PostgreSQL 16+
- **Role:** System of record for finalized game outcomes, audit trails, registered users (future phase), and administrative moderation.

---

# 4. Ergonomic Room & Lobby Management

### 4.1 Room Code Ergonomics
Room codes utilize a **6-Character Alphanumeric** scheme based on an unambiguous alphabet:
- **Alphabet:** `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (32 characters, excluding ambiguous `0`, `O`, `I`, `1`).
- **Keyspace:** $32^6 = 1,073,741,824$ (over 1 billion active combinations).
- **Collision Mitigation:** Cryptographically secure selection (`secrets.choice`) validated against active Redis room keys.
- **Direct Link Support:** Instant invite URL format: `https://uno.app/join/K7X9W2`.

### 4.2 Room Configuration Limits & Quotas
- **Min Players:** 2 | **Max Players:** 6
- **Anti-Squatting TTLs:**
  - **Lobby with 1 Player (Abandoned):** 5 minutes TTL.
  - **Lobby with $\ge 2$ Players:** 30 minutes TTL.
  - **Active Gameplay:** 10 minutes of total silence before auto-termination.
  - **Finished Match:** 15 minutes to restart before auto-closure.
- **Creation Quota:** Maximum **5 room creations per IP address per hour**.

### 4.3 Room Lifecycle State Machine

```text
                  +-------------+
                  |   CREATED   |
                  +------+------+
                         |
                         v
       +-----------------+-----------------+
       |                                   |
       v                                   v
+--------------+                   +---------------+
|   WAITING    | <---------------+ |    PLAYING    |
|   (LOBBY)    |                 | |  (IN PROGRESS)|
+-------+------+                 | +-------+-------+
        |                        |         |
        | Host triggers "Start"  |         | Normal Win or
        +------------------------+         | Abandoned Game
                                           v
                                   +---------------+
                                   |   FINISHED    |
                                   |  (PODIUM/WIN) |
                                   +-------+-------+
                                           |
                                           | Host clicks "Play Again"
                                           +---> Return to LOBBY
                                           |
                                           | Inactivity or Host "Close"
                                           v
                                   +---------------+
                                   |    CLOSED     |
                                   +---------------+
```

### 4.4 Host Authority & Failover Matrix

| Action | Host Permission | Non-Host Permission | Rules / Guardrails |
| :--- | :--- | :--- | :--- |
| **Start Game** | Allowed | Denied | Min 2 players, all players marked "Ready" (or Host override if enabled). |
| **Kick Player** | Allowed | Denied | Available only in `WAITING` lobby state. Cannot kick during active game (prevents griefing). |
| **Change House Rules** | Allowed | Denied | Can only modify settings while in lobby. |
| **End Game Early** | Allowed | Denied | Prompts confirmation modal; forces room back to `FINISHED` state. |
| **Host Disconnect** | Automatic | N/A | **Grace Window (45s):** If host returns, retains status. If timeout expires, host status passes to the player who has been in the room the longest. |

---

# 5. Authoritative UNO Rule Engine Specification

The server enforces the official Mattel UNO baseline rules, with explicit hooks for standard digital variations.

### 5.1 Card Deck Composition (Standard 108 Cards)

```text
┌────────────────────────┬───────┬───────────────────────────────────────────┐
│ Card Type              │ Count │ Color Distribution / Values               │
├────────────────────────┼───────┼───────────────────────────────────────────┤
│ Number Cards (0)       │ 4     │ 1 per color (Red, Blue, Green, Yellow)    │
│ Number Cards (1 - 9)   │ 72    │ 2 per color per number (1-9)              │
│ Skip                   │ 8     │ 2 per color                               │
│ Reverse                │ 8     │ 2 per color                               │
│ Draw Two (+2)          │ 8     │ 2 per color                               │
│ Wild                   │ 4     │ Color-neutral                             │
│ Wild Draw Four (+4)    │ 4     │ Color-neutral                             │
├────────────────────────┼───────┼───────────────────────────────────────────┤
│ TOTAL DECK             │ 108   │ 25 Red, 25 Blue, 25 Green, 25 Yellow,     │
│                        │       │ 8 Wild Cards                              │
└────────────────────────┴───────┴───────────────────────────────────────────┘
```

### 5.2 Initial Game Setup & First Card Resolution
1. **Dealing:** Every player is dealt exactly 7 cards using a Fisher-Yates cryptographically secure shuffle (`secrets.SystemRandom`).
2. **First Card Flipped from Draw Pile:**
   - **Number Card (0-9):** Normal play begins with the player to the host's left (clockwise).
   - **Action - Skip:** The first player is skipped; the second player starts.
   - **Action - Reverse:** Turn direction switches to counter-clockwise; host plays first.
   - **Action - Draw Two:** First player draws 2 cards and skips their turn.
   - **Wild:** First player chooses the active starting color.
   - **Wild Draw Four:** **Illegal as start card.** Returned to the middle of the deck, and a new first card is drawn.

### 5.3 Legality Matrix (Card Play Validation)
A card $C$ from player hand is legal to play on top card $T$ with active color $A_{color}$ if and only if:
- $C_{color} == A_{color}$, **OR**
- $C_{value} == T_{value}$ (for number cards), **OR**
- $C_{type} == T_{type}$ (for action cards: Skip, Reverse, Draw Two), **OR**
- $C_{type} == \text{"WILD"}$, **OR**
- $C_{type} == \text{"WILD\_DRAW\_FOUR"}$ (subject to optional strict rule checks).

### 5.4 Special Actions & State Transitions

#### 1. Draw Two (+2)
The next player in turn order receives 2 cards from the draw pile and is skipped.
*(Configurable House Rule: **Stacking +2 onto +2** can be toggled by the host before game start).*

#### 2. Reverse
- **2-Player Game:** Acts identical to a **Skip** card.
- **3-6 Player Game:** Inverts direction of play ($+1 \to -1$ or $-1 \to +1$).

#### 3. Skip
The next player in turn sequence misses their turn.

#### 4. Wild
The player selects one of 4 colors: `RED`, `BLUE`, `GREEN`, or `YELLOW`. The next player must match the selected color.

#### 5. Wild Draw Four (+4)
The playing player picks the next color. The next player draws 4 cards and loses their turn.

### 5.5 "UNO" Call and Challenge Engine (Critical Architecture)

```text
               Player has 2 cards and plays 1 card
                                |
                                v
               Player hand count drops to 1 card
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
Player toggled "CALL UNO"            Player FAILED to toggle
prior to / during card play          "CALL UNO" with their play
             |                                     |
             v                                     v
     [UNO Safe State]                   [UNO Vulnerable State]
Server broadcasts "Harsh called UNO!"              |
                                                   v
                                        Server opens 3.0-Second
                                        "CATCH UNO" Window for
                                        all opponents
                                                   |
                        +--------------------------+--------------------------+
                        |                                                     |
                        v                                                     v
          Opponent clicks "CATCH UNO"                        3.0 Seconds elapse with NO catch
                        |                                                     |
                        v                                                     v
          Server penalizes vulnerable player:                        Vulnerability expires;
          - Player automatically draws 2 cards                       player remains with 1 card
          - Server broadcasts penalty event                          safely into the next turn.
```

### 5.6 Fault-Tolerant Distributed Turn Timers
To ensure timers survive worker process restarts and zero game-stalling:
1. **Timestamp Deadline Architecture:**
   - Instead of volatile in-memory timers (`asyncio.sleep(25)`), the server writes an absolute millisecond timestamp into Redis:
     $$\text{turn\_deadline\_ms} = \text{now\_ms}() + 25000$$
   - The deadline is broadcast to clients, allowing client-side rendering of a smooth countdown bar that is 100% resilient to network jitter.
2. **Redis Keyspace Expiration Watcher:**
   - A Redis key is set: `SETEX uno:room:<CODE>:turn_timer 25 <current_turn_version>`.
   - If the player acts before the deadline, the key is deleted and the new turn initializes.
   - If the key expires, a background Channels worker listening to Redis expired events triggers the auto-action.
3. **Timeout Fallback Action:**
   - The server forces the player to **Draw 1 card**.
   - Turn automatically advances to the next player.
4. **AFK Strike Escalation:**
   - **Strike 1:** Turn skipped with auto-draw.
   - **Strike 2 (Consecutive):** Player is placed in `AUTO_PILOT` mode (a fast heuristic bot immediately plays the lowest playable card or draws) to maintain game momentum.
   - **Manual Resume:** The human player can click "I'm Back" at any time to regain manual control.

### 5.7 Draw Pile Depletion & Reshuffle Algorithm
When the draw pile reaches $0$:
1. The current top card of the discard pile remains in place.
2. All remaining cards in the discard pile are collected.
3. Any Wild or Wild Draw 4 cards in the discard pile have their declared color reset to neutral (`None`).
4. Cards are shuffled using cryptographic randomness (`secrets.SystemRandom`) and placed as the new draw pile.
5. Clients receive an updated `draw_pile_count` event.

---

# 6. Real-Time Communication Protocol & API

### 6.1 Two-Step Ticket Authentication Handshake
To prevent leaking sensitive session tokens into reverse proxy logs, browser histories, and WAF access logs, connection authentication follows a **Single-Use Ticket Exchange**:

```text
[Client]                                 [HTTP API]                     [WebSocket Gateway]
   |                                          |                                  |
   |-- 1. POST /api/rooms/ticket/ ----------->|                                  |
   |      (Bearer: Session Token in Header)   |                                  |
   |                                          |-- Generates 30s single-use       |
   |                                          |   ticket in Redis                |
   |<- 2. Returns { "ticket": "tkt_8a2f..." } |                                  |
   |                                                                             |
   |-- 3. Connect: wss://api.uno.app/ws/rooms/<CODE>/?ticket=tkt_8a2f... ------->|
   |                                                                             |-- Validates & atomically
   |                                                                             |   deletes ticket in Redis
   |                                                                             |-- Associates socket with player
   |<- 4. Upgraded & Initial Sanitized State Sync Broadcast <--------------------|
```

If the ticket is missing, invalid, expired, or already used, the WebSocket immediately closes with **Close Code 4003 (Unauthorized)**.

---

### 6.2 Client-to-Server Event Schemas

#### 1. Play Card (`play_card`)
```json
{
  "type": "play_card",
  "payload": {
    "card_id": "c_blue_skip_1",
    "selected_color": null,
    "call_uno": true
  }
}
```
*(Note: `selected_color` is required only if `card_id` corresponds to a Wild or Wild Draw 4).*

#### 2. Draw Card (`draw_card`)
```json
{
  "type": "draw_card",
  "payload": {}
}
```

#### 3. Catch Opponent UNO (`catch_uno`)
```json
{
  "type": "catch_uno",
  "payload": {
    "target_player_id": "p_8a92b"
  }
}
```

#### 4. Pass Turn (`pass_turn`)
*(Only valid if player has already drawn a card during the current turn)*
```json
{
  "type": "pass_turn",
  "payload": {}
}
```

#### 5. Request Full State Sync (`request_full_state_sync`)
*(Rate-limited to 1 request per 3 seconds per player)*
```json
{
  "type": "request_full_state_sync",
  "payload": {
    "last_seen_version": 41
  }
}
```

#### 6. Host Action (`host_action`)
```json
{
  "type": "host_action",
  "payload": {
    "action": "KICK_PLAYER" | "START_GAME" | "UPDATE_RULES" | "RESTART_MATCH",
    "target_player_id": "p_91f3c",
    "rules": {
      "stack_draw_two": true,
      "turn_time_seconds": 25
    }
  }
}
```

---

### 6.3 Server-to-Client Broadcast Schemas

#### 1. Sanitized Game State Sync (`game_state_sync`)
Broadcast upon initial connect, reconnection, or desync recovery. Note that each player receives their *own* sanitized view.

```json
{
  "type": "game_state_sync",
  "version": 42,
  "payload": {
    "room_code": "K7X9W2",
    "status": "PLAYING",
    "direction": 1,
    "current_player_id": "p_harsh_01",
    "turn_deadline_ms": 1773045625000,
    "top_card": {
      "id": "c_red_7_1",
      "color": "RED",
      "value": "7",
      "type": "NUMBER"
    },
    "active_color": "RED",
    "draw_pile_count": 68,
    "discard_pile_count": 12,
    "opponents": [
      {
        "player_id": "p_rahul_02",
        "nickname": "Rahul",
        "card_count": 3,
        "is_host": false,
        "connected": true,
        "uno_called": false,
        "vulnerable_uno": false
      }
    ],
    "your_hand": [
      {
        "id": "c_red_skip_0",
        "color": "RED",
        "value": "SKIP",
        "type": "ACTION",
        "is_playable": true
      },
      {
        "id": "c_wild_draw_four_2",
        "color": "WILD",
        "value": "DRAW_FOUR",
        "type": "WILD_DRAW_FOUR",
        "is_playable": true
      }
    ]
  }
}
```

#### 2. Turn Changed Event (`turn_changed`)
```json
{
  "type": "turn_changed",
  "version": 43,
  "payload": {
    "current_player_id": "p_rahul_02",
    "turn_deadline_ms": 1773045650000,
    "direction": 1
  }
}
```

#### 3. UNO Vulnerability Alert (`uno_vulnerability_window`)
```json
{
  "type": "uno_vulnerability_window",
  "payload": {
    "vulnerable_player_id": "p_rahul_02",
    "nickname": "Rahul",
    "window_ms": 3000
  }
}
```

#### 4. Error Notification (`error_event`)
```json
{
  "type": "error_event",
  "payload": {
    "code": "ILLEGAL_MOVE",
    "message": "Card color does not match active color (RED)."
  }
}
```

---

# 7. Resilient Disconnection & Reconnection Engine

Mobile network switches (e.g. 5G to Wi-Fi) cause frequent socket drops. The game guarantees state preservation through a **Reconnection Lifecycle Manager**:

```text
                        WebSocket Connection Closes
                                     |
                                     v
                  Server marks player as `DISCONNECTED`
                  Broadcasts: "Player Rahul Disconnected"
                  Starts 45-Second Grace Timer in Redis
                                     |
                 +-------------------+-------------------+
                 |                                       |
                 v                                       v
      Player reconnects within 45s             Grace Timer Expires (45s)
                 |                                       |
                 v                                       v
      Client fetches fresh ticket;            Player flagged as `ABANDONED`;
      WebSocket handshake succeeds;           Hand cards returned to draw pile
      Re-attaches to room channel;            or player replaced by Auto-Bot.
      Emits instant `game_state_sync`.        If Host: Trigger Host Migration.
```

### Self-Healing Desync via Sequence Numbers
- Every server state mutation increments an integer `version` property ($v=1, 2, 3\dots$).
- If a client detects a sequence jump (e.g., received $v=18$ when local state is $v=16$), the client dispatches:
  ```json
  { "type": "request_full_state_sync", "last_seen_version": 16 }
  ```
- The server responds with the latest sanitized snapshot, resolving all packet drop anomalies.

---

# 8. Database Architecture & Concurrency Control

PostgreSQL holds permanent records, while Redis maintains active room state manipulated via **Atomic Lua Scripts**.

### 8.1 PostgreSQL Relational Schema

```sql
-- Rooms Table
CREATE TABLE rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_code VARCHAR(6) UNIQUE NOT NULL,
    host_player_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'WAITING', -- WAITING, PLAYING, FINISHED, CLOSED
    max_players SMALLINT NOT NULL DEFAULT 6,
    house_rules JSONB DEFAULT '{"stack_draw_two": false, "turn_time_seconds": 25}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_rooms_code ON rooms(room_code) WHERE status != 'CLOSED';

-- Players / Sessions Table
CREATE TABLE room_players (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID REFERENCES rooms(id) ON DELETE CASCADE,
    session_token VARCHAR(128) UNIQUE NOT NULL,
    nickname VARCHAR(30) NOT NULL,
    seat_order SMALLINT,
    is_host BOOLEAN DEFAULT FALSE,
    is_ready BOOLEAN DEFAULT FALSE,
    connected BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_players_room_session ON room_players(room_id, session_token);

-- Match Results Table
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
    winner_player_id UUID REFERENCES room_players(id),
    total_turns INT DEFAULT 0,
    duration_seconds INT DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    final_scoreboard JSONB NOT NULL
);
```

### 8.2 Redis Active State Structure & Lua Scripting Engine
Instead of distributed locking (Redlock), all active room mutations execute via atomic Lua scripts:

#### Redis Key Layout (Per Room `K7X9W2`):
- `uno:room:K7X9W2:meta` $\to$ Hash (`status`, `host_id`, `version`, `direction`, `active_color`, `current_player_id`, `turn_deadline_ms`).
- `uno:room:K7X9W2:draw_pile` $\to$ List of serialized card strings.
- `uno:room:K7X9W2:discard_pile` $\to$ List of serialized card strings.
- `uno:room:K7X9W2:hands:<player_id>` $\to$ Set of card IDs held by player.
- `uno:room:K7X9W2:turn_timer` $\to$ String with TTL (25s).
- **Mandatory TTL Policy:** Every key under `uno:room:<CODE>:*` is initialized with a **2-hour sliding expiration (`EXPIRE`)**. Redis is configured with `maxmemory-policy volatile-lru` to prevent memory crashes.

#### Sample Atomic Play Card Lua Script (`atomic_play_card.lua`):
```lua
-- KEYS[1]: Meta Hash, KEYS[2]: Discard List, KEYS[3]: Player Hand Set
-- ARGV[1]: Player ID, ARGV[2]: Card ID, ARGV[3]: Next Player ID, ARGV[4]: New Color, ARGV[5]: Turn Deadline
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
redis.call('HSET', KEYS[1], 'current_player_id', ARGV[3], 'active_color', ARGV[4], 'turn_deadline_ms', ARGV[5])
local new_version = redis.call('HINCRBY', KEYS[1], 'version', 1)
return new_version
```

---

# 9. Frontend UX, Sound & Component Layout

### 9.1 Adaptive Virtual Game Board Layout
The game board dynamically centers the active player while arranging 1 to 5 opponents radially along the top and sides, optimized for mobile portrait and desktop landscape views.

```text
+-----------------------------------------------------------------------+
|  ROOM: K7X9W2  [Copy Link]            Direction: Clockwise [↻]        |
|                                                                       |
|                          [ Opponent 2 ]                               |
|                          Rahul (4 Cards)                              |
|                                                                       |
|   [ Opponent 1 ]                                     [ Opponent 3 ]   |
|   Ankit (6 Cards)                                    Priya (2 Cards)  |
|                                                                       |
|                                                                       |
|                        CENTER TABLE AREA                              |
|                    +-------+       +-------+                          |
|                    | DRAW  |       | [RED] |                          |
|                    | PILE  |       |   7   |                          |
|                    | (68)  |       |DISCARD|                          |
|                    +-------+       +-------+                          |
|                                                                       |
|                    Active Color Indicator: [ RED ]                    |
|                    Turn Clock: [==== 18s ====]                        |
|                                                                       |
|                                                                       |
|   [ CALL UNO ]                                       [ CATCH UNO! ]   |
|   (Armed / Safe)                                     (Target: Priya)  |
|                                                                       |
|                                                                       |
|                     YOUR HAND (Harsh - 5 Cards)                       |
|   +-----+   +-----+   +-----+   +-------+   +-------+                 |
|   | Red |   | Red |   |Blue |   | Yellow|   | Wild  |                 |
|   |  3  |   | Skip|   |  9  |   |   +2  |   |  +4   |                 |
|   +-----+   +-----+   +-----+   +-------+   +-------+                 |
|                                                                       |
+-----------------------------------------------------------------------+
```

### 9.2 Critical Sound Design Palette (Howler.js)
Sound provides visceral game feedback in real-time games. Assets loaded via web audio sprite:
- `card_play.mp3`: Subtle swoosh upon placing a card.
- `card_draw.mp3`: Crisp snap when drawing from the deck.
- `action_skip.mp3`: Heavy thud / buzzer.
- `action_reverse.mp3`: Circular whoosh effect.
- `uno_alert.mp3`: Dramatic brass bell when UNO is declared.
- `timer_tick.mp3`: Clock ticking down from 10s to 0s.
- `game_win.mp3`: Fanfare and confetti particle burst.

---

# 10. Comprehensive Quality Assurance & Test Strategy

### 10.1 Automated Test Pyramid
1. **Rule Engine Unit Tests (Target: 100% Code Coverage):**
   - Deck creation count (108 cards exact distribution).
   - Valid play rules (matching color, number, type).
   - Action effects (Skip, Reverse, Draw Two, Wild, Wild Draw Four).
   - Deck reshuffle upon draw pile starvation.
   - Winner detection and score calculation.
2. **Concurrency & Race Condition Tests:**
   - 2 players submitting a card simultaneously (Lua script atomicity verification).
   - UNO catch clicked at the exact 2.99s mark of the 3s vulnerability window.
   - Drawing card while the 25s turn timer expires.
3. **Multiplayer WebSocket Channel Tests:**
   - 6 concurrent consumers connected via Channels `WebsocketCommunicator`.
   - Card privacy leak test: Ensure `your_hand` for Player A is never broadcast in Player B's channel.
   - Abrupt socket disconnect and reconnection recovery within 45s.
4. **Security & Penetration Tests:**
   - Malformed JSON injection tests (fuzzing).
   - WebSocket frame flooding (exceeding 16KB payload limit).
   - Room code brute-force scanning rate-limit tests.

---

# 11. Phased Project Roadmap & Definition of Done

```text
WEEKS:      W1         W2         W3         W4         W5         W6
          +----------+----------+----------+----------+----------+----------+
Sprint 1: | Foundat. |          |          |          |          |          |
Sprint 2: |          | Rule Eng |          |          |          |          |
Sprint 3: |          |          | Room & WS|          |          |          |
Sprint 4: |          |          |          | Front UI |          |          |
Sprint 5: |          |          |          |          | Gameplay |          |
Sprint 6: |          |          |          |          |          | Hardening|
          +----------+----------+----------+----------+----------+----------+
```

### Sprint 1: Architecture Baseline & Database Foundation (Week 1)
- **Scope:** Repository setup, Next.js 14 skeleton, Django 5 project with ASGI Daphne configuration, Redis containerization, PostgreSQL migrations.
- **DoD (Definition of Done):** Docker Compose boots Next.js, Django, Redis, and PostgreSQL cleanly. Health-check endpoints return 200 OK.

### Sprint 2: Pure Python UNO Rule Engine & Lua Scripts (Week 2)
- **Scope:** Deck generation, card types, legal move validators, state transition engine, turn progression logic, Redis Lua script prototypes.
- **DoD:** 100% test coverage with pytest across 40+ unit test scenarios with zero external framework dependencies.

### Sprint 3: Room Lifecycle & WebSocket Ticket Handshake (Week 3)
- **Scope:** 6-character room generator, single-use ticket exchange API (`/api/rooms/ticket/`), guest session tokens, Django Channels consumer for room lobbies (join, ready, kick, start).
- **DoD:** Up to 6 simultaneous browser sessions can join the same lobby and receive real-time presence updates using ticket auth.

### Sprint 4: Responsive Frontend Table & Animation System (Week 4)
- **Scope:** Interactive game table, Framer Motion card dealing and play animations, sound effects integration, responsive hand layout.
- **DoD:** UI runs at steady 60fps on both mobile Safari/Chrome and desktop browsers with interactive mock data.

### Sprint 5: End-to-End Live Gameplay Integration (Week 5)
- **Scope:** Wire frontend store to backend Channels events. Implement timestamp turn deadlines, Draw pile depletion, Wild color selector modal, and the 3s UNO Call/Catch window.
- **DoD:** 4 human players can play a complete match from start to finish without desync or illegal moves.

### Sprint 6: Disconnection Recovery, Security Hardening & Deployment (Week 6)
- **Scope:** 45-second reconnection grace period, host migration failover, rate limiting, NGINX SSL config with 16KB frame clamping, Locust load test (100 concurrent rooms).
- **DoD:** Zero data leaks, zero stalled games during abrupt disconnects, latency < 80ms p95 under load.

---

# 12. Security, Infrastructure Hardening & Anti-Cheat Governance

### 12.1 Authentication & Ticket Security
1. **Single-Use Ticket Ingestion:** WebSocket connection requests must present a 30-second single-use ticket. Upon ingestion, the ticket key in Redis is atomically read and deleted (`GETDEL`). Replaying the ticket is impossible.
2. **Session Verification:** Actions sent over WebSocket are verified against the authenticated `player_id` locked to the socket session. Clients cannot impersonate other players.

### 12.2 Anti-DDoS, Room Squatting & Brute-Force Enumeration Protection
1. **Room Creation Throttling:** Strict rate-limiting caps room creation to **5 rooms per IP per hour**.
2. **Room Lookup Backoff:** More than 10 failed room join attempts per minute triggers a 15-minute temporary IP block.
3. **State Sync Throttling:** The `request_full_state_sync` event is throttled to **1 call per 3 seconds per player** using a token-bucket filter.
4. **WebSocket Action Throttling:** Maximum **5 actions per second per player**. Spammers receive an error notification; continuous abusers are disconnected with code `4029`.

### 12.3 NGINX Ingress & WebSocket Frame Clamping
The reverse proxy enforces tight limits to block Slowloris attacks, buffer overflows, and giant payload attacks:
```nginx
location /ws/ {
    proxy_pass http://daphne_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;

    # Defense parameters
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
    client_max_body_size 16k;        # Max frame size: 16KB
    proxy_buffering off;
}
```

### 12.4 Redis Memory Hygiene & Keyspace Eviction
1. **Volatile-LRU Policy:** Redis configuration enforces `maxmemory-policy volatile-lru`.
2. **Mandatory TTL on All Keys:** Every active room key is written with an explicit expiration (2 hours sliding window). Idle rooms automatically expire, releasing RAM.

### 12.5 Host Privilege Abuse Defenses
1. **Lobby-Only Kicking:** The host can only kick players during the `WAITING` lobby phase. Kicking during active gameplay is blocked by the server.
2. **Audit Logging:** Every kick, rule change, and match termination is written to the PostgreSQL match audit log.

### 12.6 Information Concealment & Payload Verification
1. **Zero Hand Leakage:** Opponent hands are filtered into integer counts (`card_count`). Card IDs in hands are never transmitted across the group broadcast.
2. **Draw Pile Secrecy:** The deck sequence is kept exclusively in Redis list storage. Clients never receive the draw pile order.
3. **Payload Sanitization:** Every incoming frame is parsed by strict Pydantic / DRF serializers. Any unexpected fields are rejected.

---
*End of Specification — Prepared by Senior System Designer & Security Architect for Production Execution.*
