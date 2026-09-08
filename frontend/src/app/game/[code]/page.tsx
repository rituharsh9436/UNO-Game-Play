"use client";

import { useEffect, useState, useRef, use } from "react";
import { useRouter } from "next/navigation";
import {
  Volume2,
  VolumeX,
  ArrowLeft,
  Flame,
  RotateCcw,
  Trophy,
  Users,
} from "lucide-react";
import { Card, CardColor, SanitizedGameState } from "@/types/game";
import { soundManager } from "@/lib/sounds";
import UnoCard from "@/components/game/UnoCard";
import OpponentRadial from "@/components/game/OpponentRadial";
import CenterTable from "@/components/game/CenterTable";
import PlayerHand from "@/components/game/PlayerHand";
import UnoActionControls from "@/components/game/UnoActionControls";
import WildColorPicker from "@/components/game/WildColorPicker";

export default function GameArenaPage({ params }: { params: Promise<{ code: string }> }) {
  const resolvedParams = use(params);
  const roomCode = resolvedParams.code.toUpperCase();
  const router = useRouter();

  const [session, setSession] = useState<{
    id: string;
    nickname: string;
    is_host: boolean;
    session_token: string;
  } | null>(null);

  const [gameState, setGameState] = useState<SanitizedGameState | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isArmedUno, setIsArmedUno] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);
  const [selectedWildCard, setSelectedWildCard] = useState<Card | null>(null);
  const [winnerInfo, setWinnerInfo] = useState<{ winner_nickname: string; scoreboard: Record<string, number> } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // Load session
  useEffect(() => {
    const raw = localStorage.getItem("uno_session");
    if (raw) {
      try {
        setSession(JSON.parse(raw));
      } catch {
        router.push(`/room/${roomCode}`);
      }
    } else {
      router.push(`/room/${roomCode}`);
    }
  }, [roomCode, router]);

  // Connect WebSocket with ticket
  useEffect(() => {
    if (!session?.session_token) return;

    let isMounted = true;

    const connect = async () => {
      try {
        const ticketRes = await fetch("http://127.0.0.1:8000/api/rooms/ticket/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_token: session.session_token }),
        });

        if (!ticketRes.ok) throw new Error("Ticket request failed");
        const { ticket } = await ticketRes.json();

        const ws = new WebSocket(`ws://127.0.0.1:8000/ws/rooms/${roomCode}/?ticket=${ticket}`);
        wsRef.current = ws;

        ws.onopen = () => {
          // Request initial state sync
          ws.send(JSON.stringify({ type: "request_full_state_sync", payload: {} }));
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "game_state_sync") {
              setGameState(data.payload);
            } else if (data.type === "card_played") {
              soundManager.playCard();
            } else if (data.type === "card_drawn") {
              soundManager.drawCard();
            } else if (data.type === "uno_alert") {
              soundManager.unoAlert();
            } else if (data.type === "game_finished") {
              soundManager.gameWin();
              setWinnerInfo({
                winner_nickname: data.payload.winner_nickname,
                scoreboard: data.payload.scoreboard || {},
              });
            }
          } catch (err) {
            console.error("WS error:", err);
          }
        };
      } catch (err) {
        console.error("Connection failed:", err);
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (wsRef.current) wsRef.current.close();
    };
  }, [session, roomCode]);

  // Fallback demo state for preview / offline testing
  const activeState: SanitizedGameState = gameState || {
    room_code: roomCode,
    status: "PLAYING",
    direction: 1,
    current_player_id: session?.id || "p_1",
    turn_deadline_ms: Date.now() + 25000,
    top_card: { id: "c_red_7", color: "RED", value: "7", type: "NUMBER" },
    active_color: "RED",
    draw_pile_count: 68,
    discard_pile_count: 14,
    pending_draw_count: 0,
    opponents: [
      {
        player_id: "p_2",
        nickname: "Rahul",
        card_count: 4,
        is_host: false,
        connected: true,
        uno_called: false,
        vulnerable_uno: false,
      },
      {
        player_id: "p_3",
        nickname: "Priya",
        card_count: 2,
        is_host: false,
        connected: true,
        uno_called: true,
        vulnerable_uno: false,
      },
      {
        player_id: "p_4",
        nickname: "Ankit",
        card_count: 6,
        is_host: false,
        connected: true,
        uno_called: false,
        vulnerable_uno: false,
      },
    ],
    your_hand: [
      { id: "c_red_3", color: "RED", value: "3", type: "NUMBER", is_playable: true },
      { id: "c_blue_7", color: "BLUE", value: "7", type: "NUMBER", is_playable: true },
      { id: "c_red_skip", color: "RED", value: "SKIP", type: "ACTION", is_playable: true },
      { id: "c_yellow_d2", color: "YELLOW", value: "DRAW_TWO", type: "ACTION", is_playable: false },
      { id: "c_wild_1", color: "WILD", value: "WILD", type: "WILD", is_playable: true },
    ],
  };

  const isMyTurn = activeState.current_player_id === (session?.id || "p_1");

  // Handle Card Click
  const handlePlayCard = (card: Card) => {
    if (card.color === "WILD" || card.type === "WILD" || card.type === "WILD_DRAW_FOUR") {
      setSelectedWildCard(card);
      return;
    }
    executePlay(card, null);
  };


  const executePlay = (card: Card, selectedColor: CardColor | null) => {
    soundManager.playCard();
    if (card.value === "SKIP") soundManager.actionSkip();
    if (card.value === "REVERSE") soundManager.actionReverse();

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "play_card",
          payload: {
            card_id: card.id,
            selected_color: selectedColor,
            call_uno: isArmedUno,
          },
        })
      );
    }

    // Local optimistic update for smooth 60fps UX
    setHasDrawn(false);
    setIsArmedUno(false);
    setSelectedWildCard(null);
  };

  const handleDrawCard = () => {
    soundManager.drawCard();
    setHasDrawn(true);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "draw_card", payload: {} }));
    }
  };

  const handlePassTurn = () => {
    setHasDrawn(false);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "pass_turn", payload: {} }));
    }
  };

  const handleCatchUno = (targetPlayerId: string) => {
    soundManager.unoAlert();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "catch_uno",
          payload: { target_player_id: targetPlayerId },
        })
      );
    }
  };

  const handleToggleMute = () => {
    const muted = soundManager.toggleMute();
    setIsMuted(muted);
  };

  const vulnerableOpponent = activeState.opponents.find((o) => o.vulnerable_uno) || null;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between overflow-x-hidden selection:bg-rose-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-neutral-800/80 backdrop-blur-md px-6 py-3 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/room/${roomCode}`)}
            className="p-2 rounded-xl bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-neutral-400" />
          </button>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-black tracking-wider uppercase">UNO Table</h1>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-amber-400 font-bold">
              {roomCode}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleToggleMute}
            className="p-2 rounded-xl bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 text-neutral-300 transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4 text-emerald-400" />}
          </button>
        </div>
      </header>

      {/* Main Game Arena */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-4 flex flex-col justify-between items-center gap-6 relative">
        {/* Radial Opponents Section (Arranged along top) */}
        <section className="w-full flex items-center justify-around flex-wrap gap-4 py-2">
          {activeState.opponents.map((opp, idx) => (
            <OpponentRadial
              key={opp.player_id}
              opponent={opp}
              isCurrentTurn={activeState.current_player_id === opp.player_id}
              position="top"
              onCatchUno={handleCatchUno}
            />
          ))}
        </section>

        {/* Central Arena Table */}
        <section className="my-auto py-2">
          <CenterTable
            topCard={activeState.top_card}
            activeColor={activeState.active_color}
            drawPileCount={activeState.draw_pile_count}
            discardPileCount={activeState.discard_pile_count}
            direction={activeState.direction}
            turnDeadlineMs={activeState.turn_deadline_ms}
            pendingDrawCount={activeState.pending_draw_count || 0}
            isMyTurn={isMyTurn}
            onDrawCard={handleDrawCard}
          />
        </section>

        {/* Bottom Section: Action Controls & Player Hand */}
        <section className="w-full space-y-4">
          <UnoActionControls
            isArmedUno={isArmedUno}
            canPass={hasDrawn && isMyTurn}
            vulnerableOpponent={vulnerableOpponent}
            onToggleArmUno={() => setIsArmedUno(!isArmedUno)}
            onPassTurn={handlePassTurn}
            onCatchUno={handleCatchUno}
          />

          <PlayerHand
            hand={activeState.your_hand}
            nickname={session?.nickname || "You"}
            isMyTurn={isMyTurn}
            onPlayCard={handlePlayCard}
          />
        </section>
      </main>

      {/* Wild Color Selection Modal */}
      <WildColorPicker
        isOpen={Boolean(selectedWildCard)}
        onSelectColor={(color) => {
          if (selectedWildCard) {
            executePlay(selectedWildCard, color);
          }
        }}
        onCancel={() => setSelectedWildCard(null)}
      />

      {/* Victory / Podium Modal */}
      {winnerInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-lg">
          <div className="w-full max-w-md bg-neutral-900 border border-neutral-800 p-8 rounded-3xl text-center space-y-6 shadow-2xl">
            <div className="w-16 h-16 rounded-full bg-amber-500/20 border border-amber-500/40 mx-auto flex items-center justify-center text-amber-400">
              <Trophy className="w-8 h-8 animate-bounce" />
            </div>

            <div className="space-y-2">
              <h2 className="text-3xl font-black uppercase tracking-wider text-white">
                {winnerInfo.winner_nickname} Wins!
              </h2>
              <p className="text-xs text-neutral-400">Match finished successfully.</p>
            </div>

            {/* Scoreboard */}
            <div className="p-4 rounded-2xl bg-neutral-950 border border-neutral-800 space-y-2 text-left">
              <div className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-2">
                Scoreboard
              </div>
              {Object.entries(winnerInfo.scoreboard).map(([nick, score]) => (
                <div key={nick} className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-neutral-300">{nick}</span>
                  <span className="font-mono font-bold text-amber-400">+{score} pts</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => router.push(`/room/${roomCode}`)}
              className="w-full py-3.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-xl text-sm transition-colors shadow-lg shadow-rose-600/30"
            >
              Return to Lobby
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
