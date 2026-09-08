"use client";

import { motion } from "framer-motion";
import { Wifi, WifiOff, AlertTriangle, Crown, Bot } from "lucide-react";
import { Opponent } from "@/types/game";
import UnoCard from "./UnoCard";

interface OpponentRadialProps {
  opponent: Opponent;
  isCurrentTurn: boolean;
  position: "top" | "top-left" | "top-right" | "left" | "right";
  onCatchUno?: (targetPlayerId: string) => void;
}

export default function OpponentRadial({
  opponent,
  isCurrentTurn,
  position,
  onCatchUno,
}: OpponentRadialProps) {
  // Stack card backs visually (up to 5 mini cards)
  const visibleCardsCount = Math.min(opponent.card_count, 5);

  return (
    <div className={`flex flex-col items-center gap-2 relative ${isCurrentTurn ? "scale-105" : "opacity-90"} transition-all`}>
      {/* Turn indicator glow */}
      <motion.div
        animate={isCurrentTurn ? { scale: [1, 1.05, 1], transition: { repeat: Infinity, duration: 1.5 } } : {}}
        className={`px-4 py-2 rounded-2xl border backdrop-blur-md flex items-center gap-3 transition-all ${
          isCurrentTurn
            ? "bg-neutral-900 border-amber-400/80 shadow-lg shadow-amber-400/20 ring-2 ring-amber-400/30"
            : "bg-neutral-950/80 border-neutral-800"
        }`}
      >
        {/* Connection & Avatar */}
        <div className="relative">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-neutral-800 to-neutral-700 flex items-center justify-center font-bold text-sm text-neutral-200">
            {opponent.nickname.charAt(0).toUpperCase()}
          </div>
          {opponent.is_host && (
            <span className="absolute -top-1.5 -right-1.5 bg-amber-500 text-neutral-950 p-0.5 rounded-full">
              <Crown className="w-2.5 h-2.5" />
            </span>
          )}
        </div>

        {/* Player Name & Status */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-bold text-neutral-100 max-w-[90px] truncate">
              {opponent.nickname}
            </span>
            {opponent.connected ? (
              <Wifi className="w-3 h-3 text-emerald-400" />
            ) : (
              <WifiOff className="w-3 h-3 text-rose-400 animate-pulse" />
            )}
          </div>

          <div className="flex items-center gap-1 text-[11px]">
            <span className="font-semibold text-neutral-400">
              {opponent.card_count} {opponent.card_count === 1 ? "card" : "cards"}
            </span>
            {isCurrentTurn && (
              <span className="text-[10px] font-bold text-amber-400 animate-pulse">• Turn</span>
            )}
          </div>
        </div>

        {/* UNO Badges */}
        {opponent.uno_called && (
          <span className="px-2 py-0.5 rounded bg-gradient-to-r from-rose-600 to-amber-500 text-white font-black text-[10px] tracking-wider animate-bounce shadow-md shadow-rose-600/30">
            UNO!
          </span>
        )}

        {opponent.vulnerable_uno && (
          <button
            onClick={() => onCatchUno && onCatchUno(opponent.player_id)}
            className="px-2 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-black text-[10px] tracking-wider animate-pulse flex items-center gap-1 shadow-lg shadow-rose-600/50"
          >
            <AlertTriangle className="w-3 h-3 text-yellow-300" />
            CATCH!
          </button>
        )}
      </motion.div>

      {/* Mini Card Backs Stack */}
      <div className="flex items-center -space-x-4">
        {Array.from({ length: visibleCardsCount }).map((_, idx) => (
          <motion.div
            key={idx}
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            className="transform transition-transform hover:-translate-y-1"
          >
            <UnoCard isBack size="sm" className="w-10 h-14" />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
