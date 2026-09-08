"use client";

import { motion } from "framer-motion";
import { Card } from "@/types/game";
import UnoCard from "./UnoCard";

interface PlayerHandProps {
  hand: Card[];
  nickname: string;
  isMyTurn: boolean;
  onPlayCard: (card: Card) => void;
}

export default function PlayerHand({
  hand,
  nickname,
  isMyTurn,
  onPlayCard,
}: PlayerHandProps) {
  return (
    <div className="w-full flex flex-col items-center gap-3">
      {/* Hand Header */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-wider text-neutral-400">
          Your Hand ({nickname})
        </span>
        <span className="px-2 py-0.5 rounded-full bg-neutral-900 border border-neutral-800 text-[11px] font-mono text-neutral-300">
          {hand.length} {hand.length === 1 ? "Card" : "Cards"}
        </span>
        {isMyTurn && (
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-bold animate-pulse">
            Your Turn to Play
          </span>
        )}
      </div>

      {/* Cards Scrollable / Overlapping Fan Container */}
      <div className="w-full max-w-4xl overflow-x-auto py-4 px-6 flex items-center justify-center -space-x-4 sm:-space-x-6 scrollbar-thin scrollbar-thumb-neutral-800">
        {hand.map((card, idx) => (
          <motion.div
            key={card.id || idx}
            layout
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 350, damping: 25 }}
            style={{ zIndex: idx }}
            className="flex-shrink-0"
          >
            <UnoCard
              card={card}
              size="md"
              isPlayable={isMyTurn && Boolean(card.is_playable)}
              onClick={() => onPlayCard(card)}
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
