"use client";

import { motion } from "framer-motion";
import { Brain, Cpu, Zap, Sparkles, AlertTriangle } from "lucide-react";
import type { AgentState } from "@/types";

const STATE_CONFIG: Record<
  AgentState,
  { icon: typeof Brain; label: string; accent: string }
> = {
  idle: { icon: Brain, label: "Idle", accent: "#888" },
  planning: { icon: Brain, label: "Planning research", accent: "#a78bfa" },
  deciding: { icon: Cpu, label: "Deciding next action", accent: "#60a5fa" },
  executing: { icon: Zap, label: "Executing tool", accent: "#fbbf24" },
  synthesizing: { icon: Sparkles, label: "Writing answer", accent: "#34d399" },
  completed: { icon: Sparkles, label: "Complete", accent: "#34d399" },
  error: { icon: AlertTriangle, label: "Error", accent: "#f87171" },
  aborted: { icon: AlertTriangle, label: "Stopped", accent: "#888" },
};

const ACTIVE_STATES = new Set<AgentState>([
  "planning",
  "deciding",
  "executing",
  "synthesizing",
]);

export function AgentStateBadge({ state }: { state: AgentState }) {
  const config = STATE_CONFIG[state];
  const Icon = config.icon;
  const isActive = ACTIVE_STATES.has(state);

  return (
    <motion.div
      key={state}
      initial={{ opacity: 0, y: -4, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
      style={{ background: `${config.accent}12`, color: config.accent }}
    >
      <Icon className="w-3.5 h-3.5" />
      {config.label}
      {isActive && (
        <span className="flex gap-0.5 ml-0.5">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="w-1 h-1 rounded-full"
              style={{ background: config.accent }}
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </span>
      )}
    </motion.div>
  );
}
