"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Globe,
  HardDrive,
  Database,
  Brain,
  CheckCircle2,
  Loader2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  ArrowRight,
} from "lucide-react";
import type { AgentStep, AgentPlan } from "@/types";
import { formatDuration } from "@/lib/utils";

const TOOL_META: Record<
  string,
  { icon: typeof Search; label: string; accent: string }
> = {
  web_search: { icon: Search, label: "Web Search", accent: "#60a5fa" },
  web_scrape: { icon: Globe, label: "Web Scrape", accent: "#22d3ee" },
  drive_search: { icon: HardDrive, label: "Drive Search", accent: "#34d399" },
  vector_search: { icon: Database, label: "Vector Search", accent: "#a78bfa" },
};

function StepCard({ step, index }: { step: AgentStep; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const isComplete = step.result !== null;
  const isToolStep = step.action !== null;
  const meta = isToolStep ? TOOL_META[step.action!.tool] : null;
  const ToolIcon = meta?.icon ?? Brain;
  const accent = meta?.accent ?? "#888";

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="group"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#1e1e1e] transition-colors cursor-pointer"
      >
        {/* Step number + icon */}
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${accent}15` }}
        >
          <ToolIcon className="w-3.5 h-3.5" style={{ color: accent }} />
        </div>

        {/* Label + reasoning */}
        <div className="flex-1 min-w-0 text-left">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-[var(--color-text-muted)]">
              {String(step.index + 1).padStart(2, "0")}
            </span>
            <span className="text-xs font-medium" style={{ color: accent }}>
              {isToolStep ? meta?.label ?? step.action!.tool : "Reasoning"}
            </span>
          </div>
          <p className="text-[11px] text-[var(--color-text-muted)] truncate mt-0.5">
            {step.reasoning}
          </p>
        </div>

        {/* Status + duration */}
        <div className="flex items-center gap-2 shrink-0">
          {step.durationMs != null && (
            <span className="text-[10px] font-mono text-[var(--color-text-muted)] tabular-nums">
              {formatDuration(step.durationMs)}
            </span>
          )}
          {!isComplete ? (
            <div className="w-5 h-5 rounded-md bg-[#1a1a1a] flex items-center justify-center">
              <Loader2 className="w-3 h-3 animate-spin" style={{ color: accent }} />
            </div>
          ) : step.result?.success ? (
            <div className="w-5 h-5 rounded-md bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            </div>
          ) : (
            <div className="w-5 h-5 rounded-md bg-red-500/10 flex items-center justify-center">
              <XCircle className="w-3 h-3 text-red-400" />
            </div>
          )}
          <ChevronRight
            className={`w-3 h-3 text-[var(--color-text-muted)] transition-transform ${expanded ? "rotate-90" : ""}`}
          />
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="ml-10 mr-3 pb-3 space-y-2">
              {isToolStep && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">Arguments</p>
                  <pre className="text-[11px] bg-[#141414] rounded-lg p-2.5 text-[var(--color-text-muted)] overflow-x-auto font-mono">
                    {JSON.stringify(step.action!.args, null, 2)}
                  </pre>
                </div>
              )}
              {step.result && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                    {step.result.success ? "Result" : "Error"}
                  </p>
                  <pre className={`text-[11px] bg-[#141414] rounded-lg p-2.5 overflow-x-auto max-h-40 overflow-y-auto font-mono ${step.result.success ? "text-[var(--color-text-muted)]" : "text-red-400/80"}`}>
                    {step.result.success
                      ? JSON.stringify(step.result.data, null, 2).slice(0, 2000)
                      : step.result.error}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function PlanViewer({ plan }: { plan: AgentPlan }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-xl bg-[#1a1a1a] overflow-hidden"
    >
      <div className="px-3.5 py-2.5 flex items-center gap-2">
        <Brain className="w-4 h-4 text-violet-400" />
        <span className="text-xs font-semibold text-violet-400">Research Plan</span>
        <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">{plan.steps.length} steps</span>
      </div>

      <div className="px-3.5 pb-3">
        <p className="text-xs text-[var(--color-text-muted)] mb-3 italic">{plan.analysis}</p>
        <div className="space-y-1.5">
          {plan.steps.map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: i * 0.08 }}
              className="flex items-start gap-2.5"
            >
              <div className="w-5 h-5 rounded-md bg-violet-500/10 flex items-center justify-center shrink-0 mt-px">
                <span className="text-[10px] font-mono font-bold text-violet-400">{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-xs text-[var(--color-text-secondary)]">{step.description}</span>
                {step.tool && (
                  <span className="inline-flex items-center gap-1 ml-1.5 text-[10px] text-[var(--color-text-muted)]">
                    <ArrowRight className="w-2.5 h-2.5" />
                    {step.tool}
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

interface StepViewerProps {
  steps: AgentStep[];
  plan: AgentPlan | null;
  thinking: string | null;
}

export function StepViewer({ steps, plan, thinking }: StepViewerProps) {
  const [collapsed, setCollapsed] = useState(false);
  const completedSteps = steps.filter((s) => s.result !== null).length;
  const totalTime = steps.reduce((acc, s) => acc + (s.durationMs ?? 0), 0);

  return (
    <div className="space-y-2">
      {/* Progress header */}
      {steps.length > 0 && (
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors cursor-pointer"
          >
            <ChevronDown className={`w-3 h-3 transition-transform ${collapsed ? "-rotate-90" : ""}`} />
            {collapsed ? "Show activity" : "Hide activity"}
          </button>
          <div className="flex items-center gap-2 ml-auto text-[10px] font-mono text-[var(--color-text-muted)]">
            <span>{completedSteps}/{steps.length} steps</span>
            {totalTime > 0 && (
              <span className="flex items-center gap-0.5">
                <Clock className="w-2.5 h-2.5" />
                {formatDuration(totalTime)}
              </span>
            )}
          </div>
          {/* Mini progress bar */}
          <div className="w-16 h-1 rounded-full bg-[#1a1a1a] overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-emerald-400/60"
              initial={{ width: 0 }}
              animate={{ width: steps.length > 0 ? `${(completedSteps / steps.length) * 100}%` : "0%" }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        </div>
      )}

      {!collapsed && (
        <>
          {thinking && steps.length === 0 && !plan && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-[#1a1a1a]"
            >
              <Loader2 className="w-3.5 h-3.5 text-[var(--color-text-muted)] animate-spin shrink-0" />
              <span className="text-xs text-[var(--color-text-secondary)]">{thinking}</span>
            </motion.div>
          )}

          {plan && <PlanViewer plan={plan} />}

          {steps.length > 0 && (
            <div className="space-y-0.5">
              {steps.map((step, i) => (
                <StepCard key={step.id} step={step} index={i} />
              ))}
            </div>
          )}

          {thinking && steps.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-[#1a1a1a] shimmer"
            >
              <Loader2 className="w-3.5 h-3.5 text-[var(--color-text-muted)] animate-spin shrink-0" />
              <span className="text-xs text-[var(--color-text-secondary)]">{thinking}</span>
            </motion.div>
          )}
        </>
      )}
    </div>
  );
}
