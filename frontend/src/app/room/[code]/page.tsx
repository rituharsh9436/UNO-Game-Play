"use client";

import { useEffect, useState, useRef, use } from "react";
import { useRouter } from "next/navigation";
import {
  Users,
  Shield,
  Clock,
  Play,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  UserX,
  Settings,
  ArrowLeft,
  Flame,
  Wifi,
  WifiOff,
} from "lucide-react";
import { RoomDetails, RoomParticipant } from "@/types/game";

interface LobbyPlayer {
  player_id: string;
  nickname: string;
  is_host: boolean;
  is_ready: boolean;
  connected: boolean;
  seat_order: number;
}

interface LobbyState {
  room_code: string;
  status: string;
  host_player_id: string;
  max_players: number;
  house_rules: {
    stack_draw_two?: boolean;
    turn_time_seconds?: number;
  };
  player_count: number;
  players: LobbyPlayer[];
}

export default function RoomLobbyPage({ params }: { params: Promise<{ code: string }> }) {
  const resolvedParams = use(params);
  const roomCode = resolvedParams.code.toUpperCase();
  const router = useRouter();

  const [session, setSession] = useState<{
    id: string;
    nickname: string;
    is_host: boolean;
    session_token: string;
  } | null>(null);

  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [joinNickname, setJoinNickname] = useState("");
  const [isJoining, setIsJoining] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load user session from localStorage
  useEffect(() => {
    const raw = localStorage.getItem("uno_session");
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        setSession(parsed);
      } catch {
        localStorage.removeItem("uno_session");
      }
    }
  }, []);

  // Initialize WebSocket connection using ticket auth handshake (§6.1)
  useEffect(() => {
    if (!session || !session.session_token) return;

    let isMounted = true;

    const connectWebSocket = async () => {
      try {
        // Step 1: Exchange session token for 30s single-use ticket
        const ticketRes = await fetch("http://127.0.0.1:8000/api/rooms/ticket/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_token: session.session_token }),
        });

        if (!ticketRes.ok) {
          throw new Error("Ticket exchange failed. Please rejoin room.");
        }

        const ticketData = await ticketRes.json();
        const ticket = ticketData.ticket;

        // Step 2: Open WebSocket with ticket query parameter
        const wsUrl = `ws://127.0.0.1:8000/ws/rooms/${roomCode}/?ticket=${ticket}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isMounted) return;
          setIsConnected(true);
          setErrorBanner(null);
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "lobby_state_sync") {
              setLobbyState(data.payload);
            } else if (data.type === "kicked_from_room") {
              alert("You have been kicked from the room by the host.");
              localStorage.removeItem("uno_session");
              router.push("/");
            } else if (data.type === "game_started") {
              // Match has started - will transition to table in Phase 4/5
              router.push(`/game/${roomCode}`);
            } else if (data.type === "error_event") {
              setErrorBanner(data.payload.message || data.payload.code);
            }
          } catch (e) {
            console.error("Error parsing WS frame:", e);
          }
        };

        ws.onclose = (e) => {
          if (!isMounted) return;
          setIsConnected(false);
          if (e.code === 4003) {
            setErrorBanner("Unauthorized connection: Ticket expired or invalid.");
          } else if (e.code === 4000) {
            // Kicked
          } else {
            // Auto-reconnect after 2 seconds
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, 2000);
          }
        };

        ws.onerror = () => {
          if (isMounted) setIsConnected(false);
        };
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Connection failed";
        setErrorBanner(msg);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [session, roomCode, router]);

  const handleCopyLink = () => {
    const url = `${window.location.origin}/room/${roomCode}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleToggleReady = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const myPlayer = lobbyState?.players.find((p) => p.player_id === session?.id);
    const nextState = !myPlayer?.is_ready;
    wsRef.current.send(
      JSON.stringify({
        type: "toggle_ready",
        payload: { is_ready: nextState },
      })
    );
  };

  const handleHostStartGame = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        type: "host_action",
        payload: { action: "START_GAME" },
      })
    );
  };

  const handleHostKickPlayer = (targetPlayerId: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (confirm("Are you sure you want to kick this player?")) {
      wsRef.current.send(
        JSON.stringify({
          type: "host_action",
          payload: {
            action: "KICK_PLAYER",
            target_player_id: targetPlayerId,
          },
        })
      );
    }
  };

  const handleHostUpdateRules = (stackDrawTwo: boolean, turnSeconds: number) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        type: "host_action",
        payload: {
          action: "UPDATE_RULES",
          rules: {
            stack_draw_two: stackDrawTwo,
            turn_time_seconds: turnSeconds,
          },
        },
      })
    );
  };

  const handleGuestJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!joinNickname.trim()) return;
    setIsJoining(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/rooms/${roomCode}/join/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: joinNickname.trim() }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Failed to join room.");
      }
      const data = await res.json();
      localStorage.setItem("uno_session", JSON.stringify(data.player));
      setSession(data.player);
    } catch (err: unknown) {
      setErrorBanner(err instanceof Error ? err.message : "Join error");
    } finally {
      setIsJoining(false);
    }
  };

  // If user has not joined this room yet, prompt to join
  if (!session) {
    return (
      <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-neutral-900 border border-neutral-800 p-8 rounded-2xl shadow-2xl space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-black tracking-wider uppercase">Join Room</h1>
            <p className="text-sm text-neutral-400 font-mono tracking-widest text-rose-500 font-bold">
              {roomCode}
            </p>
          </div>

          {errorBanner && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
              {errorBanner}
            </div>
          )}

          <form onSubmit={handleGuestJoin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-1.5">
                Choose Your Nickname
              </label>
              <input
                type="text"
                maxLength={30}
                placeholder="e.g. CardMaster"
                value={joinNickname}
                onChange={(e) => setJoinNickname(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-neutral-100 focus:outline-none focus:border-rose-500 text-sm"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isJoining}
              className="w-full py-3 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-xl text-sm transition-all disabled:opacity-50"
            >
              {isJoining ? "Entering Lobby..." : "Join Waiting Lobby"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const isHost = lobbyState?.host_player_id === session?.id;
  const myPlayer = lobbyState?.players.find((p) => p.player_id === session?.id);
  const otherPlayers = lobbyState?.players.filter((p) => !p.is_host) || [];
  const allOthersReady = otherPlayers.length > 0 && otherPlayers.every((p) => p.is_ready);
  const canStart = isHost && (lobbyState?.players.length || 0) >= 2 && allOthersReady;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between selection:bg-rose-500 selection:text-white">
      {/* Header */}
      <header className="border-b border-neutral-800/80 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/")}
            className="p-2 rounded-xl bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-neutral-400" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black tracking-wider uppercase">Lobby</h1>
              <span className="font-mono text-xs px-2.5 py-0.5 rounded-md bg-neutral-900 border border-neutral-800 text-amber-400 font-bold tracking-widest">
                {roomCode}
              </span>
            </div>
            <p className="text-xs text-neutral-400">Waiting for players to prepare</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleCopyLink}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 transition-all text-neutral-300"
          >
            {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copiedLink ? "Link Copied!" : "Invite Link"}
          </button>

          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border ${
              isConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-rose-500/10 text-rose-400 border-rose-500/20"
            }`}
          >
            {isConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {isConnected ? "Connected" : "Reconnecting..."}
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 space-y-6">
        {errorBanner && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center justify-between">
            <span>{errorBanner}</span>
            <button onClick={() => setErrorBanner(null)} className="text-neutral-400 hover:text-white">
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left Column: Player Slots (2 Cols) */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
                Connected Players ({lobbyState?.players.length || 0} / {lobbyState?.max_players || 6})
              </h2>
              <span className="text-xs text-neutral-500">Min 2 to start</span>
            </div>

            <div className="space-y-2.5">
              {lobbyState?.players.map((p, idx) => {
                const isMe = p.player_id === session.id;
                return (
                  <div
                    key={p.player_id}
                    className={`p-4 rounded-xl border flex items-center justify-between transition-all ${
                      isMe
                        ? "bg-neutral-900/90 border-rose-500/30 shadow-lg shadow-rose-500/5"
                        : "bg-neutral-900/60 border-neutral-800"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-neutral-800 flex items-center justify-center font-mono font-bold text-xs text-neutral-300">
                        {idx + 1}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-neutral-200">
                            {p.nickname} {isMe && "(You)"}
                          </span>
                          {p.is_host && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              HOST
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-neutral-500">
                          {p.connected ? "Connected" : "Reconnecting..."}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {p.is_host ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400">
                          <CheckCircle2 className="w-4 h-4 text-amber-400" />
                          Host Ready
                        </span>
                      ) : p.is_ready ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          Ready
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-neutral-500">
                          <Clock className="w-4 h-4 text-neutral-500" />
                          Not Ready
                        </span>
                      )}

                      {/* Host can kick other players */}
                      {isHost && !p.is_host && (
                        <button
                          onClick={() => handleHostKickPlayer(p.player_id)}
                          title="Kick Player"
                          className="p-1.5 rounded-lg bg-neutral-800/80 hover:bg-rose-500/20 text-neutral-400 hover:text-rose-400 transition-colors"
                        >
                          <UserX className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Rules & Actions */}
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
              Room Settings
            </h2>

            <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
                <span className="text-xs text-neutral-300 font-medium">Stack +2 Cards</span>
                {isHost ? (
                  <input
                    type="checkbox"
                    checked={Boolean(lobbyState?.house_rules?.stack_draw_two)}
                    onChange={(e) =>
                      handleHostUpdateRules(
                        e.target.checked,
                        lobbyState?.house_rules?.turn_time_seconds || 25
                      )
                    }
                    className="w-4 h-4 accent-rose-600 rounded cursor-pointer"
                  />
                ) : (
                  <span className="text-xs font-semibold text-neutral-400">
                    {lobbyState?.house_rules?.stack_draw_two ? "Enabled" : "Disabled"}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-300 font-medium">Turn Clock</span>
                {isHost ? (
                  <select
                    value={lobbyState?.house_rules?.turn_time_seconds || 25}
                    onChange={(e) =>
                      handleHostUpdateRules(
                        Boolean(lobbyState?.house_rules?.stack_draw_two),
                        Number(e.target.value)
                      )
                    }
                    className="bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 rounded-lg px-2 py-1 focus:outline-none focus:border-rose-500"
                  >
                    <option value={15}>15s</option>
                    <option value={25}>25s</option>
                    <option value={35}>35s</option>
                  </select>
                ) : (
                  <span className="text-xs font-semibold text-neutral-400">
                    {lobbyState?.house_rules?.turn_time_seconds || 25}s
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="pt-2">
              {isHost ? (
                <div className="space-y-2">
                  <button
                    onClick={handleHostStartGame}
                    disabled={!canStart}
                    className="w-full py-3.5 px-4 bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-rose-600/25 transition-all text-sm disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Play className="w-4 h-4 fill-white" />
                    Start Match
                  </button>
                  {!canStart && (
                    <p className="text-[11px] text-neutral-500 text-center">
                      {(lobbyState?.players.length || 0) < 2
                        ? "Waiting for at least 1 more player to join..."
                        : "Waiting for all players to mark Ready..."}
                    </p>
                  )}
                </div>
              ) : (
                <button
                  onClick={handleToggleReady}
                  className={`w-full py-3.5 px-4 font-semibold rounded-xl flex items-center justify-center gap-2 transition-all text-sm ${
                    myPlayer?.is_ready
                      ? "bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border border-neutral-700"
                      : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25"
                  }`}
                >
                  {myPlayer?.is_ready ? (
                    <>
                      <XCircle className="w-4 h-4" /> Cancel Ready
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" /> I'm Ready!
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-800/80 px-6 py-4 text-center text-xs text-neutral-500">
        Room Code: <span className="font-mono font-bold text-neutral-400">{roomCode}</span> • Zero-Trust Server Authoritative
      </footer>
    </div>
  );
}
