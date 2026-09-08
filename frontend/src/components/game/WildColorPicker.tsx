"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CardColor } from "@/types/game";

interface WildColorPickerProps {
  isOpen: boolean;
  onSelectColor: (color: CardColor) => void;
  onCancel: () => void;
}

export default function WildColorPicker({
  isOpen,
  onSelectColor,
  onCancel,
}: WildColorPickerProps) {
  if (!isOpen) return null;

  const colorOptions: { color: CardColor; label: string; bg: string; border: string; glow: string }[] = [
    {
      color: "RED",
      label: "Red",
      bg: "from-rose-600 to-red-700",
      border: "border-rose-400",
      glow: "hover:shadow-rose-600/50",
    },
    {
      color: "BLUE",
      label: "Blue",
      bg: "from-blue-600 to-indigo-700",
      border: "border-sky-400",
      glow: "hover:shadow-blue-600/50",
    },
    {
      color: "GREEN",
      label: "Green",
      bg: "from-emerald-500 to-green-700",
      border: "border-emerald-400",
      glow: "hover:shadow-emerald-600/50",
    },
    {
      color: "YELLOW",
      label: "Yellow",
      bg: "from-amber-400 to-yellow-500",
      border: "border-amber-300",
      glow: "hover:shadow-amber-500/50",
    },
  ];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
        <motion.div
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.85, opacity: 0 }}
          className="w-full max-w-sm bg-neutral-900 border border-neutral-800 p-6 rounded-3xl shadow-2xl space-y-6 text-center"
        >
          <div className="space-y-1.5">
            <h3 className="text-xl font-black uppercase tracking-wider text-neutral-100">
              Declare Color
            </h3>
            <p className="text-xs text-neutral-400">
              Choose the active color for the next player
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            {colorOptions.map((opt) => (
              <motion.button
                key={opt.color}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onSelectColor(opt.color)}
                className={`py-6 rounded-2xl bg-gradient-to-br ${opt.bg} border-2 ${opt.border} text-white font-black text-lg tracking-wider shadow-lg ${opt.glow} transition-all`}
              >
                {opt.label}
              </motion.button>
            ))}
          </div>

          <button
            onClick={onCancel}
            className="text-xs text-neutral-500 hover:text-neutral-300 font-semibold"
          >
            Cancel and choose another card
          </button>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
