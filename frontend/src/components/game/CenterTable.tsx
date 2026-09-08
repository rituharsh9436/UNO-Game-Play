"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RotateCw, RotateCcw, AlertOctagon } from "lucide-react";
import { Card, CardColor } from "@/types/game";
import UnoCard from "./UnoCard";

interface CenterTableProps {
  topCard: Card | null;
  activeColor: CardColor;
  drawPileCount: number;
  discardPileCount: number;
  direction: 1 | -1;
  turnDeadlineMs: number;
  pendingDrawCount: number;
  isMyTurn: boolean;
  onDrawCard: () => void;
}

export default function CenterTable({
  topCard,
  activeColor,
  drawPileCount,
  discardPileCount,
  direction,
  turnDeadlineMs,
  pendingDrawCount,
  isMyTurn,
  onDrawCard,
}: CenterTableProps) {
  const [secondsRemaining, setSecondsRemaining] = useState(25);
  const [percentRemaining, setPercentRemaining] = useState(100);

  // Turn timer countdown based on absolute timestamp (§5.6)
  useEffect(() => {
    if (!turnDeadlineMs) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const diff = Math.max(0, turnDeadlineMs - now);
      const secs = Math.ceil(diff / 1000);
      setSecondsRemaining(secs);
      // Assuming 25s base deadline for progress bar
      const pct = Math.min(100, Math.max(0, (diff / 25000) * 100));
      setPercentRemaining(pct);
    }, 100);

    return () => clearInterval(interval);
  }, [turnDeadlineMs]);

  // Color halo mapping
  const colorGradients: Record<CardColor, string> = {
    RED: "bg-rose-500 shadow-rose-500/50 border-rose-400 text-rose-400",
    BLUE: "bg-blue-500 shadow-blue-500/50 border-blue-400 text-blue-400",
    GREEN: "bg-emerald-500 shadow-emerald-500/50 border-emerald-400 text-emerald-400",
    YELLOW: "bg-amber-400 shadow-amber-400/50 border-amber-300 text-amber-400",
    WILD: "bg-purple-500 shadow-purple-500/50 border-purple-400 text-purple-400",
  };

  const activeColorStyle = colorGradients[activeColor] || colorGradients.RED;

  return (
    <div className="relative flex flex-col items-center justify-center p-6 rounded-3xl bg-neutral-900/40 border border-neutral-800/80 backdrop-blur-xl shadow-2xl">
      {/* Pending Stack Attack Banner */}
      {pendingDrawCount > 0 && (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="absolute -top-5 px-4 py-1 rounded-full bg-rose-600 text-white font-black text-xs tracking-wider flex items-center gap-1.5 shadow-lg shadow-rose-600/40 animate-pulse z-10"
        >
          <AlertOctagon className="w-3.5 h-3.5" />
          STACK ATTACK: +{pendingDrawCount} CARDS!
        </motion.div>
      )}

      {/* Header Info: Direction & Active Color */}
      <div className="w-full flex items-center justify-between gap-6 mb-4 text-xs font-semibold">
        {/* Direction */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-neutral-950/80 border border-neutral-800 text-neutral-300">
          {direction === 1 ? (
            <>
              <RotateCw className="w-3.5 h-3.5 text-amber-400 animate-spin-slow" />
              <span>Clockwise</span>
            </>
          ) : (
            <>
              <RotateCcw className="w-3.5 h-3.5 text-sky-400 animate-spin-slow" />
              <span>Counter-Clockwise</span>
            </>
          )}
        </div>

        {/* Active Color Banner */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-xl bg-neutral-950/80 border border-neutral-800">
          <span className="text-neutral-400 text-[11px] uppercase tracking-wider">Active Color:</span>
          <div className="flex items-center gap-1.5 font-black">
            <span className={`w-2.5 h-2.5 rounded-full ${activeColorStyle.split(" ")[0]} shadow-md`} />
            <span className={activeColorStyle.split(" ")[3]}>{activeColor}</span>
          </div>
        </div>
      </div>

      {/* Card Arena: Draw Pile & Discard Pile */}
      <div className="flex items-center justify-center gap-8 my-2">
        {/* Draw Pile */}
        <div className="flex flex-col items-center gap-2">
          <div className="relative group">
            {/* Underlying shadow cards for stack illusion */}
            <div className="absolute inset-0 bg-neutral-950 rounded-xl transform translate-x-1.5 translate-y-1.5 border border-neutral-800" />
            <div className="absolute inset-0 bg-neutral-950 rounded-xl transform translate-x-0.5 translate-y-0.5 border border-neutral-800" />

            <UnoCard
              isBack
              size="lg"
              onClick={isMyTurn ? onDrawCard : undefined}
              className={`transform transition-all ${
                isMyTurn ? "cursor-pointer group-hover:-translate-y-2 ring-2 ring-rose-500/50" : "opacity-80"
              }`}
            />
          </div>

          <div className="px-2.5 py-0.5 rounded-full bg-neutral-950 border border-neutral-800 text-[11px] font-mono text-neutral-400">
            {drawPileCount} cards
          </div>
        </div>

        {/* Discard Pile (Top Card) */}
        <div className="flex flex-col items-center gap-2">
          <AnimatePresence mode="popLayout">
            {topCard && (
              <motion.div
                key={topCard.id}
                initial={{ scale: 0.6, rotate: -20, opacity: 0 }}
                animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              >
                <UnoCard card={topCard} size="lg" />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="px-2.5 py-0.5 rounded-full bg-neutral-950 border border-neutral-800 text-[11px] font-mono text-neutral-400">
            {discardPileCount} played
          </div>
        </div>
      </div>

      {/* Turn Countdown Progress Bar */}
      <div className="w-full mt-4 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-neutral-400">
          <span>Turn Timer</span>
          <span
            className={`font-mono font-bold ${
              secondsRemaining <= 5 ? "text-rose-400 animate-pulse" : "text-neutral-300"
            }`}
          >
            {secondsRemaining}s
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-neutral-950 overflow-hidden border border-neutral-800">
          <motion.div
            className={`h-full rounded-full ${
              secondsRemaining <= 5 ? "bg-rose-500" : "bg-gradient-to-r from-rose-500 to-amber-400"
            }`}
            style={{ width: `${percentRemaining}%` }}
          />
        </div>
      </div>
    </div>
  );
}
