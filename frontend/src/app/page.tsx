"use client";

import { useState } from "react";
import { Users, Shield, Zap, Flame, ArrowRight, Play, PlusCircle } from "lucide-react";
import { API_BASE_URL } from "@/lib/config";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<"create" | "join">("create");
  const [nickname, setNickname] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [stackDrawTwo, setStackDrawTwo] = useState(false);
  const [turnTime, setTurnTime] = useState(25);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nickname.trim()) {
      setErrorMessage("Please enter your nickname.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/rooms/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: nickname.trim(),
          house_rules: {
            stack_draw_two: stackDrawTwo,
            turn_time_seconds: turnTime,
          },
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to create room.");
      }

      const data = await res.json();
      // Store session in localStorage
      localStorage.setItem("uno_session", JSON.stringify(data.player));
      window.location.href = `/room/${data.room.room_code}`;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error connecting to server.";
      setErrorMessage(`${msg} (Backend may be offline in dev mode)`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJoinRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nickname.trim()) {
      setErrorMessage("Please enter your nickname.");
      return;
    }
    if (!roomCode.trim() || roomCode.trim().length !== 6) {
      setErrorMessage("Please enter a valid 6-character room code.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const cleanCode = roomCode.trim().toUpperCase();

    try {
      const res = await fetch(`${API_BASE_URL}/api/rooms/${cleanCode}/join/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: nickname.trim(),
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to join room.");
      }

      const data = await res.json();
      localStorage.setItem("uno_session", JSON.stringify(data.player));
      window.location.href = `/room/${cleanCode}`;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error connecting to server.";
      setErrorMessage(`${msg} (Backend may be offline in dev mode)`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between selection:bg-rose-500 selection:text-white">
      {/* Header */}
      <header className="border-b border-neutral-800/80 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-red-600 via-yellow-500 to-emerald-500 p-0.5 shadow-lg shadow-red-500/20">
            <div className="w-full h-full bg-neutral-950 rounded-[10px] flex items-center justify-center">
              <Flame className="w-5 h-5 text-rose-500 fill-rose-500" />
            </div>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-wider uppercase bg-gradient-to-r from-red-500 via-amber-400 to-emerald-400 bg-clip-text text-transparent">
              UNO Multi
            </h1>
            <p className="text-xs text-neutral-400 font-medium">Real-Time Web Arena</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            v2.1 Architecture
          </span>
        </div>
      </header>

      {/* Main Hero & Action Box */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-12 flex flex-col lg:flex-row items-center justify-center gap-12">
        {/* Left Column: Value Prop */}
        <div className="flex-1 space-y-6 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-neutral-900 border border-neutral-800 text-neutral-300">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            Zero Registration • Instant 6-Char Code
          </div>

          <h2 className="text-4xl sm:text-5xl font-black tracking-tight leading-tight">
            The Ultimate Real-Time <br />
            <span className="bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400 bg-clip-text text-transparent">
              Server-Authoritative
            </span>{" "}
            UNO
          </h2>

          <p className="text-neutral-400 text-base sm:text-lg max-w-xl">
            Drop in with 2 to 6 players instantly. Powered by pure-Python authoritative rules, Redis Lua atomicity, and smooth 60fps card play.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800/80">
              <Shield className="w-5 h-5 text-emerald-400 mb-2" />
              <h3 className="text-sm font-semibold text-neutral-200">Zero Cheat</h3>
              <p className="text-xs text-neutral-400 mt-1">Opponent hands & draw pile never leak to clients.</p>
            </div>
            <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800/80">
              <Zap className="w-5 h-5 text-amber-400 mb-2" />
              <h3 className="text-sm font-semibold text-neutral-200">Anti-Stall</h3>
              <p className="text-xs text-neutral-400 mt-1">Distributed 25s deadline timer & bot fallback.</p>
            </div>
            <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800/80">
              <Users className="w-5 h-5 text-sky-400 mb-2" />
              <h3 className="text-sm font-semibold text-neutral-200">Reconnection</h3>
              <p className="text-xs text-neutral-400 mt-1">45-second self-healing grace window.</p>
            </div>
          </div>
        </div>

        {/* Right Column: Room Action Card */}
        <div className="w-full max-w-md bg-neutral-900/90 border border-neutral-800 p-6 rounded-2xl shadow-2xl backdrop-blur-xl">
          {/* Tabs */}
          <div className="grid grid-cols-2 p-1 bg-neutral-950 rounded-xl border border-neutral-800 mb-6">
            <button
              onClick={() => {
                setActiveTab("create");
                setErrorMessage(null);
              }}
              className={`py-2 text-sm font-semibold rounded-lg flex items-center justify-center gap-2 transition-all ${
                activeTab === "create"
                  ? "bg-rose-600 text-white shadow-md shadow-rose-600/30"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              <PlusCircle className="w-4 h-4" />
              Create Room
            </button>
            <button
              onClick={() => {
                setActiveTab("join");
                setErrorMessage(null);
              }}
              className={`py-2 text-sm font-semibold rounded-lg flex items-center justify-center gap-2 transition-all ${
                activeTab === "join"
                  ? "bg-rose-600 text-white shadow-md shadow-rose-600/30"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              <Play className="w-4 h-4" />
              Join Room
            </button>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
              {errorMessage}
            </div>
          )}

          {activeTab === "create" ? (
            <form onSubmit={handleCreateRoom} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-1.5">
                  Your Nickname
                </label>
                <input
                  type="text"
                  maxLength={30}
                  placeholder="e.g. MasterShuffler"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition-all text-sm"
                  required
                />
              </div>

              <div className="p-3.5 rounded-xl bg-neutral-950/60 border border-neutral-800/80 space-y-3">
                <div className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                  House Rules
                </div>

                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs text-neutral-300 font-medium">Stack Draw Two (+2 on +2)</span>
                  <input
                    type="checkbox"
                    checked={stackDrawTwo}
                    onChange={(e) => setStackDrawTwo(e.target.checked)}
                    className="w-4 h-4 accent-rose-600 rounded cursor-pointer"
                  />
                </label>

                <div className="flex items-center justify-between">
                  <span className="text-xs text-neutral-300 font-medium">Turn Deadline</span>
                  <select
                    value={turnTime}
                    onChange={(e) => setTurnTime(Number(e.target.value))}
                    className="bg-neutral-900 border border-neutral-800 text-xs text-neutral-200 rounded-lg px-2 py-1 focus:outline-none focus:border-rose-500"
                  >
                    <option value={15}>15 seconds</option>
                    <option value={25}>25 seconds (Default)</option>
                    <option value={35}>35 seconds</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 px-4 bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-rose-600/25 transition-all text-sm disabled:opacity-50"
              >
                {isSubmitting ? "Creating..." : "Create Room & Invite Friends"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <form onSubmit={handleJoinRoom} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-1.5">
                  Your Nickname
                </label>
                <input
                  type="text"
                  maxLength={30}
                  placeholder="e.g. CardNinja"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition-all text-sm"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-1.5">
                  6-Character Room Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="e.g. K7X9W2"
                  value={roomCode}
                  onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                  className="w-full px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-neutral-100 placeholder-neutral-500 uppercase tracking-widest text-center font-mono font-bold focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition-all text-base"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 px-4 bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-rose-600/25 transition-all text-sm disabled:opacity-50"
              >
                {isSubmitting ? "Joining..." : "Enter Room Lobby"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-800/80 px-6 py-4 text-center text-xs text-neutral-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <span>Real-Time Multiplayer UNO Web Platform • Version 2.1 Baseline</span>
        <div className="flex items-center gap-4">
          <a
            href={`${API_BASE_URL}/api/health/`}
            target="_blank"
            rel="noreferrer"
            className="hover:text-neutral-300 transition-colors"
          >
            Backend Health API
          </a>
          <a
            href="/api/health"
            target="_blank"
            rel="noreferrer"
            className="hover:text-neutral-300 transition-colors"
          >
            Frontend Health API
          </a>
        </div>
      </footer>
    </div>
  );
}
