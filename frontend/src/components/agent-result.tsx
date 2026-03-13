"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  ExternalLink,
  FileText,
  Clock,
  Footprints,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Download,
  Share2,
  Coins,
  Check,
  Zap,
  BarChart3,
  TrendingUp,
} from "lucide-react";
import type { AgentResult, Citation, TokenUsage } from "@/types";
import { formatDuration } from "@/lib/utils";

/* ── Animated counter hook ─────────────────────────────── */

function useCountUp(target: number, duration = 1200) {
  const [value, setValue] = useState(0);
  const ref = useRef<number>(0);

  useEffect(() => {
    const start = performance.now();
    const from = ref.current;
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = from + (target - from) * eased;
      setValue(current);
      if (progress < 1) requestAnimationFrame(step);
      else ref.current = target;
    };
    requestAnimationFrame(step);
  }, [target, duration]);

  return value;
}

function AnimatedNumber({ value, decimals = 0, prefix = "", suffix = "" }: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}) {
  const animated = useCountUp(value);
  return (
    <span className="tabular-nums">
      {prefix}{decimals > 0 ? animated.toFixed(decimals) : Math.round(animated).toLocaleString()}{suffix}
    </span>
  );
}

/* ── Analytics Panel ───────────────────────────────────── */

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.2 } },
};

const popIn = {
  hidden: { opacity: 0, y: 12, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

function AnalyticsPanel({ result, usage }: { result: AgentResult; usage?: TokenUsage }) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="mt-4 rounded-xl bg-[#1a1a1a] overflow-hidden"
    >
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-2">
        <BarChart3 className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
        <span className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
          Analytics
        </span>
      </div>

      {/* Stats grid */}
      <div className="px-3 pb-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {/* Duration */}
          <motion.div variants={popIn} className="p-3 rounded-lg bg-[#141414]">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Clock className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">Time</span>
            </div>
            <p className="text-lg font-bold text-cyan-400 tabular-nums">
              {formatDuration(result.durationMs)}
            </p>
          </motion.div>

          {/* Steps */}
          <motion.div variants={popIn} className="p-3 rounded-lg bg-[#141414]">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Footprints className="w-3 h-3 text-violet-400" />
              <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">Steps</span>
            </div>
            <p className="text-lg font-bold text-violet-400">
              <AnimatedNumber value={result.totalSteps} />
            </p>
          </motion.div>

          {/* Tokens */}
          {usage && (
            <motion.div variants={popIn} className="p-3 rounded-lg bg-[#141414]">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Zap className="w-3 h-3 text-amber-400" />
                <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">Tokens</span>
              </div>
              <p className="text-lg font-bold text-amber-400">
                <AnimatedNumber value={usage.totalTokens} />
              </p>
              <div className="flex gap-2 mt-1">
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  In: {usage.promptTokens.toLocaleString()}
                </span>
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  Out: {usage.completionTokens.toLocaleString()}
                </span>
              </div>
              {/* Token ratio bar */}
              <div className="flex h-1 rounded-full overflow-hidden mt-1.5 bg-[#1a1a1a]">
                <div
                  className="bg-amber-500/40 rounded-l-full"
                  style={{ width: `${(usage.promptTokens / usage.totalTokens) * 100}%` }}
                />
                <div
                  className="bg-amber-300/40 rounded-r-full"
                  style={{ width: `${(usage.completionTokens / usage.totalTokens) * 100}%` }}
                />
              </div>
            </motion.div>
          )}

          {/* Cost */}
          {usage && (
            <motion.div variants={popIn} className="p-3 rounded-lg bg-[#141414]">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Coins className="w-3 h-3 text-emerald-400" />
                <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">Cost</span>
              </div>
              <p className="text-lg font-bold text-emerald-400">
                $<AnimatedNumber value={usage.estimatedCost} decimals={4} />
              </p>
              <div className="flex items-center gap-1 mt-1">
                <TrendingUp className="w-2.5 h-2.5 text-emerald-500/50" />
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  ${(usage.estimatedCost / Math.max(result.totalSteps, 1)).toFixed(5)}/step
                </span>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ── Citation ──────────────────────────────────────────── */

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <motion.a
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      href={citation.url ?? "#"}
      target={citation.url ? "_blank" : undefined}
      rel="noopener noreferrer"
      className={`block px-3 py-2.5 rounded-xl bg-[#1a1a1a] hover:bg-[#222222] transition-colors group ${
        citation.url ? "cursor-pointer" : "cursor-default"
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-[10px] font-mono text-[var(--color-text-muted)] bg-[#262626] rounded px-1.5 py-0.5 shrink-0 mt-0.5">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h4 className="text-sm text-[var(--color-text-secondary)] truncate">{citation.title}</h4>
            {citation.url && (
              <ExternalLink className="w-3 h-3 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
            )}
          </div>
          {citation.snippet && (
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{citation.snippet}</p>
          )}
          <span className="inline-block mt-1 text-[10px] text-[var(--color-text-muted)] bg-[#262626] rounded px-1.5 py-0.5">
            {citation.source.replace("_", " ")}
          </span>
        </div>
      </div>
    </motion.a>
  );
}

/* ── Markdown ──────────────────────────────────────────── */

function renderMarkdown(text: string): string {
  let html = text
    .replace(/^### (.*$)/gm, "<h3>$1</h3>")
    .replace(/^## (.*$)/gm, "<h2>$1</h2>")
    .replace(/^# (.*$)/gm, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code>$1</code>")
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    )
    .replace(/^\- (.*$)/gm, "<li>$1</li>")
    .replace(/^\d+\. (.*$)/gm, "<li>$1</li>")
    .replace(/^> (.*$)/gm, "<blockquote>$1</blockquote>");

  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`);
  html = html.replace(/\n\n/g, "</p><p>");
  html = `<p>${html}</p>`;
  html = html.replace(/<p><h([123])>/g, "<h$1>").replace(/<\/h([123])><\/p>/g, "</h$1>");
  html = html.replace(/<p><ul>/g, "<ul>").replace(/<\/ul><\/p>/g, "</ul>");
  html = html.replace(/<p><blockquote>/g, "<blockquote>").replace(/<\/blockquote><\/p>/g, "</blockquote>");

  return html;
}

/* ── Export Actions ────────────────────────────────────── */

function ExportActions({ result, runId }: { result: AgentResult; runId?: string }) {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = (key: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(null), 2000);
    });
  };

  const handleCopyMarkdown = () => {
    const md = [
      result.answer,
      "",
      result.citations.length > 0 ? "## Sources" : "",
      ...result.citations.map((c, i) => `${i + 1}. [${c.title}](${c.url ?? "#"}) — ${c.source}`),
    ]
      .filter(Boolean)
      .join("\n");
    copy("md", md);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.4 }}
      className="flex items-center gap-1"
    >
      <button
        onClick={handleCopyMarkdown}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[#1e1e1e] transition-all cursor-pointer"
      >
        {copied === "md" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
        {copied === "md" ? "Copied!" : "Copy"}
      </button>
      <button
        onClick={() => window.print()}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[#1e1e1e] transition-all cursor-pointer"
      >
        <Download className="w-3 h-3" />
        PDF
      </button>
      {runId && (
        <button
          onClick={() => copy("share", `${window.location.origin}/share/${runId}`)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[#1e1e1e] transition-all cursor-pointer"
        >
          {copied === "share" ? <Check className="w-3 h-3 text-emerald-400" /> : <Share2 className="w-3 h-3" />}
          {copied === "share" ? "Copied!" : "Share"}
        </button>
      )}
    </motion.div>
  );
}

/* ── Main Result View ──────────────────────────────────── */

interface AgentResultViewProps {
  result: AgentResult;
  usage?: TokenUsage;
  runId?: string;
}

export function AgentResultView({ result, usage, runId }: AgentResultViewProps) {
  return (
    <div className="space-y-3">
      {/* Status indicator */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="inline-flex items-center gap-1.5 text-xs"
      >
        {result.status === "completed" ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        )}
        <span className={result.status === "completed" ? "text-emerald-400" : "text-amber-400"}>
          Research {result.status === "completed" ? "complete" : result.status}
        </span>
      </motion.div>

      {/* Answer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="prose max-w-none"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(result.answer) }}
      />

      {/* Citations */}
      {result.citations.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="space-y-2 pt-2"
        >
          <div className="flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
            <span className="text-xs font-medium text-[var(--color-text-muted)]">
              {result.citations.length} sources
            </span>
          </div>
          <div className="grid grid-cols-1 gap-1.5">
            {result.citations.map((c, i) => (
              <CitationCard key={i} citation={c} index={i} />
            ))}
          </div>
        </motion.div>
      )}

      {/* Analytics Panel */}
      <AnalyticsPanel result={result} usage={usage} />

      {/* Export actions */}
      <div className="flex justify-end pt-1">
        <ExportActions result={result} runId={runId} />
      </div>
    </div>
  );
}
