# Multiplayer UNO — Project Documentation

## 1. Project Overview

This project is a real-time multiplayer UNO web application that allows friends to play together from anywhere.

The application will support:

- Private rooms
- A unique 10-digit numeric room code
- Up to 6 players per room
- A host-controlled lobby
- Real-time gameplay
- Standard UNO rules
- Player nicknames
- Host management of the room
- Server-authoritative game validation
- Rejoining/reconnection support
- PostgreSQL persistence where appropriate

The project is intended to be a web application accessible from desktop and mobile browsers.

---

# 2. Technology Stack

## Frontend

**Next.js**

Responsibilities:

- Application UI
- Robust WebSocket Management (e.g., using `react-use-websocket` or a global React Context to ensure a single stable connection, avoiding duplicate connections on component remounts)
- Landing page
- Create-room flow
- Join-room flow
- Lobby
- Player list
- Host controls
- UNO game table
- Player hand
- Card interactions
- Turn indicators
- Game notifications
- WebSocket connection to the backend
- Rendering the current server-provided game state

The frontend must not be considered authoritative for game rules.

---

## Backend

**Python Django**

**Django REST Framework** will be used for conventional HTTP APIs.

Responsibilities:

- Room creation
- Room joining
- Room management
- Player/session management
- Host authorization
- Game lifecycle
- UNO game state
- UNO rule validation
- WebSocket communication
- Persistence
- Reconnection handling
- Security and validation

Django is the authoritative server for the game.

---

## Database

**PostgreSQL**

PostgreSQL will store persistent information. It integrates seamlessly with Django's ORM and Admin Panel, making it a better fit than a NoSQL database. Unstructured data like game state snapshots can utilize PostgreSQL's `JSONField`.

Data to persist:

- Rooms
- Players/session metadata where necessary
- Match information
- Match results
- Relevant game history, if enabled

Live gameplay state should not be unnecessarily written to PostgreSQL after every UI action.

---

## Real-Time Communication

**WebSockets using Django Channels**

WebSockets are the preferred communication mechanism because UNO is a real-time multiplayer game.

A persistent WebSocket connection will allow the server to immediately notify all players when:

- Someone joins
- Someone leaves
- A player is kicked
- The host starts the game
- A card is played
- A card is drawn
- A wild-card color is selected
- The turn changes
- A player calls UNO
- Someone wins
- The game ends

For production scaling across multiple Django instances, a shared **Redis channel layer** should be used with Django Channels.

---

# 3. High-Level Architecture

```text
                         INTERNET
                            |
                            |
                    +-------v-------+
                    |    Next.js    |
                    |   Frontend   |
                    +-------+-------+
                            |
                 +----------+----------+
                 |                     |
              HTTPS                WebSocket
                 |                     |
                 +----------+----------+
                            |
                    +-------v-------+
                    |     Django     |
                    | REST + Channels|
                    +-------+-------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
       Room Manager     UNO Logic     Authentication
             |              |
             +-------+------+
                     |
                     v
                 +-------+
                 |PostgreSQL|
                 +-------+

             Production scaling:
                 Django
                    |
                  Redis
                    |
             Channels Layer
```

---

# 4. Core Design Principle

The most important architectural principle is:

> The server is authoritative.

The browser can request an action, but it cannot decide whether that action is valid.

For example:

```text
Player
   |
   | "Play red 7"
   v
Next.js
   |
   | WebSocket
   v
Django
   |
   +--> Is it this player's turn?
   |
   +--> Does the player have this card?
   |
   +--> Is the card playable?
   |
   +--> Is the requested action legal?
   |
   +--> Apply card effect
   |
   +--> Update game state
   |
   +--> Advance turn
   |
   v
Broadcast updated state
   |
   +----------+----------+
   |                     |
   v                     v
Player A              Player B
```

This prevents players from modifying the frontend to perform illegal moves.

---

# 5. Why WebSockets?

Normal HTTP follows a request-response pattern:

```text
Client -> Server
Client <- Server
```

That is inconvenient for a multiplayer game because clients would have to repeatedly poll the server.

WebSockets provide a persistent connection:

```text
Client <=================> Server
```

The server can push events immediately.

For example:

```text
Player A plays a card
        |
        v
     Django
        |
        +----> Player A
        +----> Player B
        +----> Player C
        +----> Player D
```

All connected players receive the updated game state without repeatedly requesting it.

---

# 6. Room System

A room is a private game session.

Each room has a unique 10-digit numeric code.

Example:

```text
7391846251
```

The room code is the mechanism through which friends find and enter the room.

## Room Requirements

- Exactly 10 digits
- Numeric only
- Unique among active rooms
- Maximum 6 players
- A room has exactly one host
- A player cannot join a full room
- A player cannot join a room that is closed
- A player cannot join an already-started game unless reconnection is supported for that player
- Abandoned rooms should eventually expire

## Room Code Generation

The server should generate the room code.

Example conceptual implementation:

```python
import secrets

def generate_room_code():
    return f"{secrets.randbelow(10_000_000_000):010d}"
```

The generated code must still be checked against active rooms before being accepted.

The room code should never be treated as a secret authentication credential.

---

# 7. Host System

The player who creates the room becomes the host.

The host manages the room lobby.

## Host Permissions Before Game Starts

The host can:

- View all players
- Kick players
- Start the game
- Close the room

Potential future options:

- Change game settings
- Enable/disable optional rules
- Set a player limit below 6

## Host Permissions During the Game

Host privileges should be more restricted.

The host may:

- End the game
- Return players to lobby
- Restart the game
- Handle room-level administration

The host must not be able to:

- Add arbitrary cards to a hand
- Change another player's cards
- Change the current turn arbitrarily
- Declare a winner
- Modify the deck
- Bypass UNO rules

All game-state changes remain controlled by the server.

---

# 8. Host Authentication

The room code must not be sufficient to identify the host.

Bad design:

```text
Room Code + "start_game"
```

A malicious player who knows the room code could attempt to perform host actions.

Instead, the server should associate each player with a session/player identity.

Example:

```text
Create Room
     |
     +--> Room Code
     |
     +--> Player ID / Session
     |
     +--> Host status
```

When the client sends:

```json
{
  "type": "start_game"
}
```

Django verifies:

```text
Is the connection authenticated?
        |
        v
Is this player the host?
        |
        v
Is the room still in lobby state?
        |
        v
Are the game-start conditions satisfied?
        |
        v
Start game
```

---

# 9. Player System

Players do not initially need full user accounts.

A player can enter a nickname.

Example:

```text
Nickname: Harsh
```

A player receives a server-side identity/session.

Example conceptual object:

```json
{
  "player_id": "generated-id",
  "nickname": "Harsh",
  "room_code": "7391846251",
  "is_host": true,
  "connected": true
}
```

## Player Requirements

- Unique player ID within a room
- Nickname
- Host status
- Connection status
- Ready status if a ready system is implemented

Nicknames should be validated and sanitized by the server.

---

# 10. Room Lifecycle

A room can move through several states.

```text
CREATED
   |
   v
WAITING
   |
   | Host starts
   v
PLAYING
   |
   v
FINISHED
   |
   v
CLOSED
```

Suggested room statuses:

```text
waiting
playing
finished
closed
```

## Waiting

Players can:

- Join
- Leave
- Be kicked
- Wait for the host

The host can start the game.

## Playing

Players participate in the UNO game.

Normal lobby actions are restricted.

## Finished

The game has a winner.

Players can potentially:

- Start another round
- Return to lobby
- Leave

## Closed

The room can no longer be joined.

---

# 11. Lobby Flow

## Host Flow

```text
Open Website
     |
     v
Create Room
     |
     v
Enter Nickname
     |
     v
Room Created
     |
     v
10-Digit Code Displayed
     |
     v
Share Code
     |
     v
Players Join
     |
     v
Host Manages Lobby
     |
     v
Start Game
```

## Joiner Flow

```text
Open Website
     |
     v
Join Room
     |
     v
Enter Nickname
     |
     v
Enter 10-Digit Code
     |
     v
Django validates room
     |
     v
Join Lobby
     |
     v
Wait for Host
     |
     v
Game Starts
```

---

# 12. Lobby UI

Example:

```text
+--------------------------------------+
|              UNO                     |
|                                      |
| Room Code                            |
| 7391846251                           |
|                                      |
| Players (4/6)                        |
|                                      |
| 👑 Harsh        HOST                 |
|    Rahul                             |
|    Ankit                             |
|    Priya                             |
|                                      |
| [ Start Game ]                       |
|                                      |
| Share the 10-digit code with friends |
+--------------------------------------+
```

The host should see management controls beside players:

```text
Harsh     HOST
Rahul     [Kick]
Ankit     [Kick]
Priya     [Kick]
```

Normal players should not see host-only controls.

The backend must still enforce these permissions even if a user manipulates the frontend.

---

# 13. UNO Game

The application will implement standard UNO-style gameplay.

The server maintains the authoritative game state.

Typical state includes:

```text
Players
Player hands
Draw pile
Discard pile
Current player
Turn direction
Current color
Current top card
Game status
Pending card effect
Winner
```

Conceptual game state:

```json
{
  "room_code": "7391846251",
  "status": "playing",
  "current_player_id": "player-1",
  "direction": 1,
  "current_color": "red",
  "top_card": {
    "color": "red",
    "value": "7"
  },
  "players": [],
  "draw_pile_count": 73
}
```

The actual private card information must not be exposed to other players.

---

# 14. Card Privacy

This is extremely important.

A player's hand is private.

The server must not broadcast:

```json
{
  "players": [
    {
      "name": "Rahul",
      "hand": [
        "red_7",
        "blue_skip",
        "wild"
      ]
    }
  ]
}
```

to everyone.

Instead, each client should receive a player-specific view.

For example, Player A receives:

```json
{
  "your_hand": [
    "red_7",
    "blue_skip",
    "wild"
  ]
}
```

While other players receive only:

```json
{
  "player_id": "rahul",
  "nickname": "Rahul",
  "card_count": 3
}
```

This prevents players from inspecting other players' cards through browser developer tools or WebSocket messages.

---

# 15. UNO Rules

The server should validate all moves.

Typical card categories:

```text
Number cards
Skip
Reverse
Draw Two
Wild
Wild Draw Four
```

The game logic should handle:

- Valid card placement
- Turn order
- Direction
- Skip effects
- Reverse effects
- Draw Two effects
- Wild color selection
- Wild Draw Four restrictions
- Drawing cards
- Reshuffling when the draw pile is exhausted
- Winning
- UNO calls
- End of round

The exact rule set should be finalized before implementation so that all behavior is consistent.

---

# 16. Game Logic Structure

No external game engine is required.

The UNO logic can be ordinary Python code.

Suggested conceptual structure:

```text
backend/
│
├── rooms/
│   ├── models/
│   ├── services/
│   ├── consumers/
│   └── ...
│
└── game/
    ├── deck.py
    ├── cards.py
    ├── rules.py
    ├── state.py
    ├── actions.py
    └── ...
```

Possible functions:

```python
create_deck()
shuffle_deck()
deal_cards()
is_valid_move()
play_card()
draw_card()
apply_card_effect()
advance_turn()
choose_color()
check_winner()
reshuffle_discard_pile()
```

The game module should be independent from WebSocket code as much as practical.

This makes it easier to test the UNO rules separately.

---

# 17. WebSocket Architecture

Each active game room should have a WebSocket group.

Conceptually:

```text
/ws/rooms/<room_code>/
```

All players in the same room connect to the same logical channel/group.

Example:

```text
Room 7391846251

        Django Channels
              |
      +-------+-------+
      |       |       |
    Harsh   Rahul   Ankit
```

When one player performs an action, Django validates it and broadcasts the appropriate result to the room.

---

# 18. WebSocket Events

Suggested client-to-server events:

```text
join_room
leave_room
player_ready
start_game
kick_player
close_room

play_card
draw_card
choose_color
call_uno

end_game
restart_game
```

Suggested server-to-client events:

```text
room_state
player_joined
player_left
player_kicked
player_ready
game_started

card_played
card_drawn
color_changed
turn_changed

uno_called
player_won
game_finished

error
room_closed
host_changed
player_reconnected
player_disconnected
```

These event names are suggestions and can be changed during implementation.

---

# 19. Example WebSocket Action

Client sends:

```json
{
  "type": "play_card",
  "card_id": "red_7"
}
```

Server performs (acquiring a lock, e.g. via Redis, to prevent concurrent race conditions):

```text
1. Identify player
2. Identify room
3. Verify room is playing
4. Verify it is player's turn
5. Verify player owns the card
6. Verify card can legally be played
7. Remove card from hand
8. Add card to discard pile
9. Apply card effect
10. Update current color if required
11. Determine next player
12. Check winner
13. Broadcast updated state
```

If invalid:

```json
{
  "type": "error",
  "code": "INVALID_MOVE",
  "message": "This card cannot be played."
}
```

The server should not trust any client-provided game state.

---

# 20. REST API vs WebSocket

Use REST for operations that do not require continuous real-time communication.

Examples:

```text
POST /api/rooms/
POST /api/rooms/<code>/join/
GET  /api/rooms/<code>/
```

Use WebSockets for live room/game operations.

Examples:

```text
play_card
draw_card
choose_color
kick_player
start_game
player_joined
player_left
turn_changed
```

This gives the project a clean separation:

```text
HTTP
 |
 +-- Room creation
 +-- Room lookup
 +-- Initial data
 +-- Non-real-time operations

WebSocket
 |
 +-- Live room events
 +-- Gameplay
 +-- State updates
 +-- Presence
```

---

# 21. PostgreSQL Data Design

The exact schema will be implemented using Django Models.

A conceptual Room model:
- `id`: UUID (Primary Key)
- `room_code`: CharField (10 digits, Unique)
- `host_id`: CharField (Reference to Player session)
- `status`: CharField (waiting, playing, finished, closed)
- `created_at`: DateTimeField
- `updated_at`: DateTimeField
- `state`: JSONField (Optional, for storing serialized live game state)

A conceptual Player model:
- `id`: UUID (Primary Key)
- `room`: ForeignKey(Room)
- `player_id`: CharField (Session identifier)
- `nickname`: CharField
- `is_host`: BooleanField
- `user_id`: ForeignKey(User, null=True)

A Match model could contain:
- `id`: UUID (Primary Key)
- `room`: ForeignKey(Room)
- `winner_id`: CharField
- `started_at`: DateTimeField
- `finished_at`: DateTimeField

The exact database representation should be optimized after the application flow is finalized, leveraging Django's relational integrity and `JSONField` flexibility.

---

# 22. Live State vs Persistent State

Not everything needs to be stored in PostgreSQL continuously.

## Live State

```text
Current turn
Draw pile
Discard pile
Player hands
Direction
Current color
Temporary effects
```

This is actively manipulated during gameplay.

## Persistent State

```text
Room
Players
Match
Winner
Results
Timestamps
```

This can be persisted in PostgreSQL.

The goal is to avoid unnecessary database writes for every card interaction.

---

# 23. Reconnection

A real multiplayer game must handle temporary network failures.

Example:

```text
Player
   |
   | Internet disconnects
   v
Django marks player disconnected
   |
   v
Other players see:
"Rahul disconnected"
   |
   | Rahul reconnects
   v
Django identifies Rahul's session
   |
   v
Current game state is sent
```

The player's hand and game position should remain intact during a reasonable reconnection window.

A player should not automatically lose their cards merely because their browser briefly disconnected.

## Session Persistence on Refresh
To survive browser refreshes or accidental tab closes, the server must generate a secure `session_token` upon room join. The Next.js client stores this token in `localStorage` or an HTTP-Only Cookie. Upon reconnecting, the client re-authenticates using this token to regain its existing player identity.

---

# 24. Disconnect Handling

Possible behavior:

## Lobby

If a player disconnects:

```text
Player leaves lobby
```

If the host disconnects, the application should define a host transfer policy.

Recommended:

```text
Host disconnects
      |
      v
Temporary grace period
      |
      +-- reconnects --> remains host
      |
      +-- does not reconnect --> transfer host
```

Host transfer can select the next eligible player.

## During Game

A disconnected player should remain associated with the game for a defined grace period.

If they fail to reconnect, the game can apply a defined inactive-player policy.

This policy should be explicitly implemented rather than leaving undefined behavior.

---

# 25. Room Security

The room code is not authentication.

Security should include:

- Server-side player identity
- Host authorization
- WebSocket authentication
- Input validation
- Nickname sanitization
- Room capacity enforcement
- Game-state validation
- Rate limiting where appropriate
- Protection against unauthorized host actions
- Protection against invalid WebSocket events

Never trust:

```text
Player ID
Host flag
Card ownership
Current turn
Room status
```

when supplied directly by the client.

The server should determine these values.

---

# 26. Room Capacity

Maximum:

```text
6 players
```

The server must enforce this.

Example:

```text
Players: 6/6

New player attempts to join
        |
        v
Django checks capacity
        |
        v
Reject
```

Client message:

```json
{
  "type": "error",
  "code": "ROOM_FULL",
  "message": "This room is full."
}
```

---

# 27. Invalid Room Handling

When a player enters a room code, the server should check:

```text
Does room exist?
Is room closed?
Is room full?
Has game already started?
Is joining allowed?
```

Possible responses:

```text
ROOM_NOT_FOUND
ROOM_FULL
GAME_ALREADY_STARTED
ROOM_CLOSED
INVALID_ROOM_CODE
```

---

# 28. Frontend Pages

Suggested Next.js structure:

```text
/
├── Home
│
├── /create
│   └── Create Room
│
├── /join
│   └── Join Room
│
├── /room/[roomCode]
│   └── Lobby
│
└── /room/[roomCode]/game
    └── Game
```

The exact routing structure can be changed if a different Next.js architecture is preferred.

---

# 29. Frontend Components

Possible components:

```text
RoomCodeInput
NicknameInput
CreateRoomForm
JoinRoomForm

Lobby
PlayerList
PlayerCard
HostControls
RoomCodeDisplay

GameTable
PlayerArea
OpponentArea
Card
Hand
DrawPile
DiscardPile
TurnIndicator
ColorPicker
GameNotification
UNOButton
GameOverModal
```

The frontend should derive its display from the server state rather than maintaining an independent authoritative game state.

---

# 30. Game UI

A typical game layout:

```text
                    Player 2
                 [ 5 cards ]

        Player 3              Player 4
       [4 cards]             [7 cards]


             DRAW     DISCARD
             PILE      PILE


        Player 5              Player 6
       [3 cards]             [6 cards]


                  YOU
        [5] [Red Skip] [Wild] [9] [2]
```

The UI should adapt for:

- Desktop
- Tablet
- Mobile

The player's hand should remain easy to interact with on touch devices.

---

# 31. Error Handling

Errors should be represented using predictable codes.

Example:

```json
{
  "type": "error",
  "code": "NOT_YOUR_TURN",
  "message": "It is not your turn."
}
```

Possible errors:

```text
INVALID_ROOM_CODE
ROOM_NOT_FOUND
ROOM_FULL
ROOM_CLOSED
NOT_HOST
GAME_ALREADY_STARTED
GAME_NOT_STARTED
NOT_YOUR_TURN
CARD_NOT_IN_HAND
INVALID_CARD
INVALID_COLOR
INVALID_ACTION
PLAYER_NOT_FOUND
```

The frontend should convert these into user-friendly notifications.

---

# 32. State Synchronization

The server should be able to send a complete sanitized game state to a player.

## Handling Dropped Packets & Desync
To handle potential dropped WebSocket packets, the server should maintain a **State Version** or **Sequence Number**. 
Each state update broadcasted increments this version. If a client receives an event with a version higher than expected (e.g., received Version 5 while local state is Version 3), the client should immediately emit a `request_full_state_sync` event to fetch the correct state.

Example:

```json
{
  "room": {
    "code": "7391846251",
    "status": "playing"
  },
  "players": [
    {
      "id": "player-1",
      "name": "Harsh",
      "card_count": 5
    },
    {
      "id": "player-2",
      "name": "Rahul",
      "card_count": 3
    }
  ],
  "your_hand": [
    {
      "id": "card-12",
      "color": "red",
      "value": "7"
    }
  ],
  "top_card": {
    "color": "blue",
    "value": "5"
  },
  "current_color": "blue",
  "current_player_id": "player-2",
  "direction": 1
}
```

Notice that other players' actual cards are never exposed.

---

# 33. Room Code Sharing

The lobby should make sharing easy.

Example:

```text
Join my UNO game!

Room Code:
7391846251
```

A copy button can be provided.

However, the application should not depend on clipboard APIs for core functionality. Manual copying/sharing must remain possible.

---

# 34. Deployment Architecture

Initial deployment can be:

```text
                Users
                  |
             Internet
                  |
        +---------+---------+
        |                   |
        v                   v
     Next.js              Django
     Hosting              Server
                            |
                  +---------+---------+
                  |                   |
                  v                   v
               PostgreSQL             Redis
```

Next.js serves the frontend.

Django handles:

- REST
- WebSockets
- Rooms
- Game logic

PostgreSQL stores persistent data.

Redis acts as the shared channel layer when multiple Django instances are used.

---

# 35. Scaling Considerations

For up to 6 players per room, individual rooms are lightweight.

The primary scaling concern is not the number of players in one room but the number of simultaneous rooms.

A scalable architecture is:

```text
                 Load Balancer
                      |
          +-----------+-----------+
          |           |           |
       Django      Django      Django
          |           |           |
          +-----------+-----------+
                      |
                    Redis
                      |
                   PostgreSQL
```

Django Channels uses Redis to coordinate WebSocket events across server instances.

---

# 36. Testing Strategy

The UNO rules should be tested independently of the frontend.

## Unit Tests

Test:

```text
Deck creation
Deck size
Shuffle
Card dealing
Valid moves
Invalid moves
Skip
Reverse
Draw Two
Wild
Wild Draw Four
Turn progression
Direction
Drawing
Reshuffling
Winner detection
UNO calls
```

## Multiplayer Tests

Test:

```text
Create room
Join room
Six-player capacity
Seventh player rejected
Host permissions
Kick player
Start game
Player disconnect
Player reconnect
Invalid WebSocket actions
Concurrent actions
Game completion
```

## Security Tests

Test:

```text
Non-host attempts host action
Player plays another player's card
Player plays out of turn
Player sends fake player ID
Player sends fake room state
Player sends invalid card
Player attempts to join full room
```

---

# 37. Suggested Development Phases

## Phase 1 — Project Foundation

Set up:

```text
Next.js
Django
Django REST Framework
PostgreSQL
Django Channels
```

Establish environment configuration and basic project structure.

---

## Phase 2 — Room System

Implement:

```text
Create room
Generate 10-digit code
Join room
Leave room
Room capacity
Host identification
Room status
```

---

## Phase 3 — Lobby

Implement:

```text
Player list
Host controls
Kick player
Close room
Start game
Real-time lobby updates
```

---

## Phase 4 — UNO Logic

Implement and test:

```text
Deck
Cards
Hands
Turns
Move validation
Card effects
Drawing
Reshuffling
Winner
```

This logic should be independent of the UI.

---

## Phase 5 — Multiplayer Gameplay

Connect the UNO logic to Django Channels.

Implement:

```text
play_card
draw_card
choose_color
UNO call
turn updates
game state synchronization
```

---

## Phase 6 — Reconnection

Implement:

```text
Disconnect detection
Session persistence
Reconnect
Game-state resynchronization
Host reconnection
Host transfer
```

---

## Phase 7 — UI/UX

Polish:

```text
Game table
Cards
Animations
Turn indicators
Notifications
Mobile layout
Lobby
Game-over screen
```

---

## Phase 8 — Production Hardening

Implement:

```text
Authentication/session security
Rate limiting
Validation
Logging
Error monitoring
PostgreSQL indexes
Redis
WebSocket scaling
Room expiration
```

---

# 38. Important Architectural Rules

The following rules should be maintained throughout development.

### Rule 1 — Server is authoritative

Never trust the frontend for game decisions.

### Rule 2 — Room code is not authentication

The 10-digit code identifies the room, not the authority of the user.

### Rule 3 — Cards are private

Never broadcast another player's hand.

### Rule 4 — Game logic is independent

Keep UNO rules separate from WebSocket transport code.

### Rule 5 — WebSockets handle live state

Do not poll the backend unnecessarily for gameplay updates.

### Rule 6 — PostgreSQL is not the real-time event bus

Use Django Channels and Redis for real-time communication when scaling.

### Rule 7 — Validate every action

Every WebSocket command must be validated on the server.

### Rule 8 — Room capacity is server-enforced

Never rely on the frontend to enforce the 6-player limit.

---

# 39. Initial MVP

The first working version should contain only:

```text
Landing page
    |
    +-- Create Room
    |
    +-- Join Room

Create Room
    |
    +-- 10-digit code
    +-- Host

Lobby
    |
    +-- Up to 6 players
    +-- Player list
    +-- Kick
    +-- Start Game

Game
    |
    +-- Standard UNO deck
    +-- Player hands
    +-- Turns
    +-- Play card
    +-- Draw card
    +-- Wild color
    +-- Card effects
    +-- UNO
    +-- Winner

Real-time
    |
    +-- WebSockets
    +-- Player join/leave
    +-- Gameplay updates
    +-- Reconnection

Persistence
    |
    +-- PostgreSQL
```

Avoid adding accounts, leaderboards, matchmaking, chat, friends lists, or other features until the core multiplayer game is stable.

---


---

# 42. Player Account and Identity Management

Player identity should be separated from the concept of a persistent user account.

The MVP should not require players to create an account before playing.

The desired experience is:

```text
Open Website
     |
     v
Enter Nickname
     |
     v
Create / Join Room
     |
     v
Play UNO
```

This keeps the game frictionless for friends who simply want to play together.

---

## 42.1 Guest Players

A guest player can join without registering.

When a player enters a nickname, Django creates a temporary player identity/session.

Conceptual representation:

```json
{
  "player_id": "p_8f31...",
  "nickname": "Harsh",
  "session_id": "...",
  "room_code": "7391846251",
  "is_host": true
}
```

The `player_id` is generated by the server.

The nickname is only a display name and must never be used as the player's unique identity.

For example, two players may both choose:

```text
Harsh
```

but they must still have different:

```text
player_id
```

---

## 42.2 Player ID vs User ID

The application should distinguish between a game/session player and a persistent account.

```text
player_id
    |
    +-- Identifies a player in a game/session

user_id
    |
    +-- Identifies a permanent registered account
```

A guest player may have:

```json
{
  "player_id": "p_123",
  "user_id": null,
  "nickname": "Harsh"
}
```

A registered player may have:

```json
{
  "player_id": "p_456",
  "user_id": "u_789",
  "nickname": "Harsh"
}
```

This separation makes the system flexible and allows account functionality to be introduced later without redesigning the multiplayer system.

---

## 42.3 Registered Accounts

Persistent accounts can be added after the MVP.

A registered account can contain:

```text
User
├── user_id
├── username
├── email
├── password_hash
├── created_at
└── statistics
```

Registered accounts can later support:

- Persistent profile
- Game history
- Statistics
- Win rate
- Leaderboards
- Friends
- Avatars
- Persistent username
- Other social features

Django's authentication system should be used for registered users rather than implementing password authentication manually.

---

## 42.4 Guest and Registered Players

The final architecture can support both:

```text
                       PLAYER
                          |
             +------------+------------+
             |                         |
           Guest                   Registered
             |                         |
        player_id                 player_id
        session                   user_id
        nickname                  account
             |                         |
             +------------+------------+
                          |
                          v
                         ROOM
                          |
                          v
                         GAME
```

A room does not need to care whether a player is a guest or registered.

The room primarily needs the player's game identity:

```text
player_id
nickname
is_host
connection status
```

If an account exists, it can additionally reference:

```text
user_id
```

---

## 42.5 Session Management

Guest sessions should use a secure server-generated session identifier or equivalent signed/secure authentication mechanism.

The client should not be able to arbitrarily choose:

```text
player_id
is_host
user_id
```

The server determines these values.

The session should allow Django to associate a WebSocket connection with the correct player.

Conceptually:

```text
Browser
   |
   | Session
   v
Django
   |
   +--> player_id
   +--> room_code
   +--> host status
```

---

## 42.6 Host Identity

Creating a room automatically makes the creating player the host.

The server stores the host identity:

```text
Room
├── room_code
├── host_id
└── players[]
```

The host is identified using the server-side player identity, not the nickname or room code.

Example:

```json
{
  "room_code": "7391846251",
  "host_id": "p_123"
}
```

When a host-only action is requested:

```text
Player sends:
    start_game

        |
        v

Django identifies player
        |
        v
Compare player_id with room.host_id
        |
        +---- Match ----> Allow
        |
        +---- No match -> Reject
```

---

## 42.7 Reconnection and Sessions

The player identity/session should survive a temporary WebSocket disconnect.

Example:

```text
Player
   |
   | WebSocket disconnects
   v
Django
   |
   | Keep player associated with game
   v
Player reconnects
   |
   v
Django identifies existing session
   |
   v
Send current sanitized game state
```

This prevents a temporary internet or browser connection problem from immediately destroying the player's game state.

A reasonable reconnection grace period should be defined during implementation.

---

## 42.8 Guest Session Expiration

Guest identities should not remain indefinitely.

A guest session can expire when:

- The player leaves the room
- The game is finished
- The room is closed
- The session remains inactive beyond the defined expiration period

Room and session cleanup should be handled automatically.

---

## 42.9 Account Management — Future Phase

Account registration should be treated as a future feature rather than an MVP requirement.

Recommended progression:

```text
MVP
 |
 +-- Guest nickname
 +-- Server-generated player ID
 +-- Secure session
 +-- Room participation
 +-- Reconnection
 |
 v
Future
 |
 +-- User registration
 +-- Login
 +-- Persistent profile
 +-- Game history
 +-- Statistics
 +-- Friends
 +-- Leaderboards
```

This keeps the first version simple while leaving a clean path for a full account system.

---

## 42.10 Identity Rules

The following rules should always be maintained:

### Rule 1 — Nicknames are not identities

```text
nickname != player identity
```

### Rule 2 — Player IDs are server-generated

Clients must not be able to select arbitrary player IDs.

### Rule 3 — Room codes are not authentication

Knowing the 10-digit room code does not make a player the host.

### Rule 4 — Host status is server-controlled

The frontend only displays host privileges. Django enforces them.

### Rule 5 — Guest accounts should be temporary

Guest sessions should eventually expire.

### Rule 6 — Registered accounts are optional

Playing UNO should not require registration in the MVP.

### Rule 7 — WebSocket connections must be associated with player identity

Every WebSocket action must be tied to the authenticated/validated player session.

---

# 43. Updated Player Data Model

A conceptual room player object is:

```json
{
  "player_id": "p_123",
  "user_id": null,
  "nickname": "Harsh",
  "is_host": true,
  "is_ready": true,
  "connected": true
}
```

For a registered user:

```json
{
  "player_id": "p_456",
  "user_id": "u_789",
  "nickname": "Rahul",
  "is_host": false,
  "is_ready": true,
  "connected": true
}
```

The `player_id` represents the current game participant.

The optional `user_id` links that participant to a persistent account.

---

# 44. Updated Overall Architecture

The complete conceptual architecture is now:

```text
                         INTERNET
                            |
                            |
                    +-------v-------+
                    |    Next.js    |
                    |   Frontend   |
                    +-------+-------+
                            |
                 +----------+----------+
                 |                     |
              HTTPS                WebSocket
                 |                     |
                 +----------+----------+
                            |
                    +-------v-------+
                    |     Django     |
                    | REST + Channels|
                    +-------+-------+
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
   Authentication     Room Manager        UNO Logic
          |                 |                  |
          |                 +------------------+
          |                            |
          +----------------------------+
                       |
              +--------+--------+
              |                 |
              v                 v
           PostgreSQL            Redis
                         (production
                       Channels layer)
```

Player identity flows through the entire system:

```text
Browser
   |
   v
Guest Session / User Account
   |
   v
Player ID
   |
   v
Room
   |
   v
Game
```

The key architectural separation remains:

```text
Next.js
= Interface

Django
= Authority + Room Management + Game Logic

PostgreSQL
= Persistent Data

WebSockets / Django Channels
= Real-Time Communication

Redis
= Shared Channels Infrastructure for Scaling
```

# 40. Final Technology Decision

The current agreed stack is:

```text
Frontend
└── Next.js

Backend
├── Django
├── Django REST Framework
└── Django Channels

Database
└── PostgreSQL

Real-time
└── WebSockets
    └── Django Channels

Production WebSocket scaling
└── Redis

Deployment
├── Next.js hosting
└── Django application server
```

No separate game-engine framework is required.

The UNO game engine will simply be a set of well-tested Python modules responsible for maintaining and validating the game's state.

---

# 41. Key Principle

The application should be thought of as:

```text
             NEXT.JS
                |
        User Interface
                |
                | WebSocket
                v
             DJANGO
                |
       +--------+--------+
       |                 |
       v                 v
   ROOM SYSTEM       UNO LOGIC
       |                 |
       +--------+--------+
                |
                v
             MONGODB
```

Django is the brain of the multiplayer game.

Next.js is the interface.

PostgreSQL provides persistence.

WebSockets provide the real-time connection.

Redis can provide the shared real-time infrastructure when the backend is scaled horizontally.
