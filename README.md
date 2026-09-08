# Real-Time Multiplayer UNO Web Platform

> **Modern, low-latency, server-authoritative multiplayer UNO web game built with Next.js, Django Channels, Redis, and PostgreSQL.**

For a comprehensive architectural breakdown and product specification, please refer to:
* [Project Brief](file:///D:/Project/UNO/UNO-Game-Play/PROJECT_BRIEF.md) — Executive summary, technical architecture, security pillars, and feature matrix.
* [System Specification (`docs.md`)](file:///D:/Project/UNO/UNO-Game-Play/docs.md) — Comprehensive v2.1 system and engineering specifications.

---

## Highlights

* **Instant Guest Onboarding:** No accounts or downloads needed; jump into matches in 15 seconds via clean 6-character room codes (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`).
* **Absolute Server Authority:** Pure Python game engine runs 100% of deck mutations and rule validation server-side. Zero client-side card peeking.
* **Atomic Concurrency:** Single-threaded Redis Lua scripts prevent race conditions and duplicate card draws.
* **Resilient Play:** Turn deadlines, 45-second reconnect grace periods, and automatic bot takeovers prevent stalled games.
* **Modern Radial UI:** Next.js 14 App Router, Tailwind CSS, Framer Motion animations, and Howler.js spatial sound effects.

---

## Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/rituharsh9436/UNO-Game-Play.git
cd UNO-Game-Play

# Spin up all containers
docker compose up --build -d
```

Access points:
* **Frontend Game UI:** [http://localhost:3000](http://localhost:3000) (or via NGINX at [http://localhost](http://localhost))
* **Backend REST API:** [http://localhost:8000/api/](http://localhost:8000/api/)
