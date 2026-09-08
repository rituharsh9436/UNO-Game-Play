"use client";

import { motion } from "framer-motion";
import { Ban, RefreshCw, Layers } from "lucide-react";
import { Card, CardColor, CardValue } from "@/types/game";

interface UnoCardProps {
  card?: Card | null;
  isBack?: boolean;
  isPlayable?: boolean;
  size?: "sm" | "md" | "lg";
  onClick?: () => void;
  className?: string;
}

export default function UnoCard({
  card,
  isBack = false,
  isPlayable = false,
  size = "md",
  onClick,
  className = "",
}: UnoCardProps) {
  // Dimensions
  const sizeClasses = {
    sm: "w-14 h-20 text-xs rounded-lg border-[2px]",
    md: "w-20 h-32 text-sm rounded-xl border-[3px]",
    lg: "w-28 h-44 text-lg rounded-2xl border-[4px]",
  }[size];

  // Card Back (Draw Pile / Opponent Cards)
  if (isBack || !card) {
    return (
      <div
        onClick={onClick}
        className={`${sizeClasses} bg-neutral-900 border-neutral-700 flex items-center justify-center p-1.5 shadow-xl relative overflow-hidden select-none ${
          onClick ? "cursor-pointer hover:border-neutral-500 transition-colors" : ""
        } ${className}`}
      >
        <div className="w-full h-full bg-gradient-to-tr from-neutral-950 via-neutral-900 to-neutral-800 rounded-lg border border-neutral-700/60 flex items-center justify-center relative overflow-hidden">
          <div className="w-16 h-28 bg-gradient-to-tr from-rose-600 via-amber-500 to-rose-600 rounded-full transform -rotate-45 flex items-center justify-center shadow-inner opacity-90">
            <span className="font-black italic text-white tracking-tighter text-sm drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
              UNO
            </span>
          </div>
        </div>
      </div>
    );
  }

  // Card Backgrounds
  const colorGradients: Record<CardColor, string> = {
    RED: "from-rose-600 via-red-600 to-rose-700 border-rose-300 text-rose-600 shadow-rose-600/30",
    BLUE: "from-blue-600 via-sky-600 to-indigo-700 border-sky-300 text-blue-600 shadow-blue-600/30",
    GREEN: "from-emerald-500 via-green-600 to-emerald-700 border-emerald-300 text-emerald-600 shadow-emerald-600/30",
    YELLOW: "from-amber-400 via-yellow-400 to-amber-500 border-amber-200 text-amber-500 shadow-amber-500/30",
    WILD: "from-neutral-900 via-neutral-950 to-black border-neutral-400 text-neutral-900 shadow-purple-600/30",
  };

  const gradient = colorGradients[card.color] || colorGradients.RED;

  // Render Card Value/Symbol
  const renderSymbol = (isCorner = false) => {
    switch (card.value) {
      case "SKIP":
        return <Ban className={isCorner ? "w-3 h-3" : "w-7 h-7"} />;
      case "REVERSE":
        return <RefreshCw className={isCorner ? "w-3 h-3" : "w-6 h-6"} />;
      case "DRAW_TWO":
        return <span className={`font-black ${isCorner ? "text-[10px]" : "text-xl"}`}>+2</span>;
      case "WILD":
        if (isCorner) return <span className="text-[9px] font-black">W</span>;
        return (
          <div className="w-8 h-8 rounded-full border border-white/40 grid grid-cols-2 overflow-hidden shadow-md">
            <div className="bg-rose-500" />
            <div className="bg-sky-500" />
            <div className="bg-amber-400" />
            <div className="bg-emerald-500" />
          </div>
        );
      case "DRAW_FOUR":
        return (
          <div className="flex flex-col items-center justify-center">
            <span className={`font-black ${isCorner ? "text-[9px]" : "text-lg"} text-white drop-shadow`}>
              +4
            </span>
          </div>
        );
      default:
        return <span className={`font-black ${isCorner ? "text-xs" : "text-2xl"}`}>{card.value}</span>;
    }
  };

  return (
    <motion.div
      whileHover={isPlayable ? { y: -16, scale: 1.06, transition: { duration: 0.15 } } : undefined}
      whileTap={isPlayable ? { scale: 0.95 } : undefined}
      onClick={isPlayable ? onClick : undefined}
      className={`relative select-none ${sizeClasses} bg-gradient-to-br ${gradient} p-1 shadow-lg ${
        isPlayable
          ? "cursor-pointer ring-2 ring-white ring-offset-2 ring-offset-neutral-950"
          : "opacity-85"
      } ${className}`}
    >
      {/* Corner Values */}
      <div className="absolute top-1 left-1.5 flex flex-col items-center leading-none text-white drop-shadow font-mono font-black">
        {renderSymbol(true)}
      </div>
      <div className="absolute bottom-1 right-1.5 flex flex-col items-center leading-none text-white drop-shadow font-mono font-black rotate-180">
        {renderSymbol(true)}
      </div>

      {/* Central Slanted White Oval */}
      <div className="w-full h-full rounded-lg bg-white/95 flex items-center justify-center shadow-inner relative overflow-hidden transform -rotate-6">
        <div className="transform rotate-6 flex items-center justify-center">
          {renderSymbol(false)}
        </div>
      </div>
    </motion.div>
  );
}
