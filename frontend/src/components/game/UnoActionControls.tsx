"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Check, ShieldAlert, SkipForward } from "lucide-react";

interface UnoActionControlsProps {
  isArmedUno: boolean;
  canPass: boolean;
  vulnerableOpponent: { player_id: string; nickname: string } | null;
  onToggleArmUno: () => void;
  onPassTurn: () => void;
  onCatchUno: (targetPlayerId: string) => void;
}

export default function UnoActionControls({
  isArmedUno,
  canPass,
  vulnerableOpponent,
  onToggleArmUno,
  onPassTurn,
  onCatchUno,
}: UnoActionControlsProps) {
  return (
    <div className="flex items-center justify-center gap-4 flex-wrap">
      {/* CALL UNO Button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={onToggleArmUno}
        className={`px-6 py-3 rounded-2xl font-black text-sm uppercase tracking-wider flex items-center gap-2 shadow-xl transition-all ${
          isArmedUno
            ? "bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-neutral-950 ring-4 ring-amber-400/40 shadow-amber-400/30 scale-105"
            : "bg-gradient-to-r from-rose-600 to-red-700 text-white shadow-rose-600/30 hover:from-rose-500 hover:to-red-600"
        }`}
      >
        {isArmedUno ? (
          <>
            <Check className="w-4 h-4 stroke-[3]" />
            UNO Armed (Safe)
          </>
        ) : (
          <>
            <ShieldAlert className="w-4 h-4" />
            Arm UNO Call
          </>
        )}
      </motion.button>

      {/* CATCH UNO Button (Pulsing when an opponent missed UNO) */}
      {vulnerableOpponent && (
        <motion.button
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: [1, 1.08, 1], opacity: 1, transition: { repeat: Infinity, duration: 1 } }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onCatchUno(vulnerableOpponent.player_id)}
          className="px-6 py-3 rounded-2xl bg-gradient-to-r from-red-600 to-rose-700 text-white font-black text-sm uppercase tracking-wider flex items-center gap-2 shadow-2xl ring-4 ring-rose-500/50 shadow-rose-600/60"
        >
          <AlertTriangle className="w-4 h-4 text-yellow-300" />
          CATCH {vulnerableOpponent.nickname.toUpperCase()}! (+2 Penalty)
        </motion.button>
      )}

      {/* Pass Turn Button (Enabled after drawing) */}
      {canPass && (
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onPassTurn}
          className="px-5 py-3 rounded-2xl bg-neutral-900 border border-neutral-700 hover:bg-neutral-800 text-neutral-200 font-bold text-sm flex items-center gap-2 transition-colors shadow-lg"
        >
          <SkipForward className="w-4 h-4" />
          Pass Turn
        </motion.button>
      )}
    </div>
  );
}
