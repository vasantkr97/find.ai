"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Clock,
  Footprints,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Trash2,
  ChevronDown,
  BarChart3,
  ArrowLeft,
  Coins,
} from "lucide-react";
import { formatDuration } from "@/lib/utils";
import { apiFetch } from "@/lib/api-client";

interface HistoryRun {
  id: string;
  task: string;
  answer: string | null;
  status: string;
  totalSteps: number;
  durationMs: number;
  promptTokens: number;
  completionTokens: number;
  estimatedCost: number;
  conversationId: string | null;
  createdAt: string;
}

interface Stats {
  totalRuns: number;
  completedRuns: number;
  successRate: number;
  avgDurationMs: number;
  totalTokens: number;
  totalCost: number;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="w-4 h-4 text-emerald-500/60" />;
    case "error":
      return <XCircle className="w-4 h-4 text-red-500/60" />;
    case "step_limit":
      return <AlertTriangle className="w-4 h-4 text-amber-500/60" />;
    case "running":
      return <Loader2 className="w-4 h-4 text-[var(--color-text-muted)] animate-spin" />;
    default:
      return <Clock className="w-4 h-4 text-[var(--color-text-muted)]" />;
  }
}

function StatsBar({ stats }: { stats: Stats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {[
        { label: "Total Queries", value: stats.totalRuns.toString(), icon: BarChart3 },
        { label: "Success Rate", value: `${(stats.successRate * 100).toFixed(0)}%`, icon: CheckCircle2 },
        { label: "Avg Duration", value: formatDuration(stats.avgDurationMs), icon: Clock },
        { label: "Total Cost", value: `$${stats.totalCost.toFixed(4)}`, icon: Coins },
      ].map(({ label, value, icon: Icon }) => (
        <div key={label} className="p-4 rounded-2xl bg-[var(--color-card)]">
          <div className="flex items-center gap-2 mb-1.5">
            <Icon className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
            <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">{label}</span>
          </div>
          <p className="text-xl font-bold text-[var(--color-text)]">{value}</p>
        </div>
      ))}
    </div>
  );
}

function HistoryItem({ run, onDelete }: { run: HistoryRun; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="rounded-2xl bg-[var(--color-card)] overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--color-card-hover)] transition-colors cursor-pointer"
      >
        <StatusIcon status={run.status} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--color-text)] truncate">{run.task}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-muted)]">
            <span>{new Date(run.createdAt).toLocaleDateString()}</span>
            <span className="flex items-center gap-1">
              <Footprints className="w-3 h-3" />
              {run.totalSteps}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(run.durationMs)}
            </span>
            {run.estimatedCost > 0 && (
              <span>${run.estimatedCost.toFixed(4)}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(run.id);
            }}
            className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <ChevronDown
            className={`w-4 h-4 text-[var(--color-text-muted)] transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      <AnimatePresence>
        {expanded && run.answer && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1">
              <div className="prose prose-sm max-w-none text-[var(--color-text-muted)] max-h-48 overflow-y-auto">
                <p className="whitespace-pre-wrap text-sm">{run.answer.slice(0, 1000)}</p>
                {run.answer.length > 1000 && (
                  <Link
                    href={`/share/${run.id}`}
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)] text-xs mt-2 inline-block"
                  >
                    View full result &rarr;
                  </Link>
                )}
              </div>
              {(run.promptTokens > 0 || run.completionTokens > 0) && (
                <div className="flex items-center gap-4 mt-3 pt-3 text-xs text-[var(--color-text-muted)]">
                  <span>Prompt: {run.promptTokens.toLocaleString()}</span>
                  <span>Completion: {run.completionTokens.toLocaleString()}</span>
                  <span>Total: {(run.promptTokens + run.completionTokens).toLocaleString()}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function HistoryPage() {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const fetchRuns = useCallback(
    async (cursor?: string) => {
      const params = new URLSearchParams({ stats: "true", limit: "20" });
      if (search) params.set("search", search);
      if (cursor) params.set("cursor", cursor);

      const res = await apiFetch(`/api/history?${params}`);
      const data = await res.json();

      if (cursor) {
        setRuns((prev) => [...prev, ...data.items]);
      } else {
        setRuns(data.items);
        if (data.stats) setStats(data.stats);
      }
      setNextCursor(data.nextCursor);
    },
    [search]
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchRuns().finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchRuns]);

  const handleDelete = async (id: string) => {
    await apiFetch(`/api/history/${id}`, { method: "DELETE" });
    setRuns((prev) => prev.filter((r) => r.id !== id));
    if (stats) setStats({ ...stats, totalRuns: stats.totalRuns - 1 });
  };

  const handleLoadMore = async () => {
    if (!nextCursor) return;
    setLoadingMore(true);
    await fetchRuns(nextCursor);
    setLoadingMore(false);
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <nav className="sticky top-0 z-50 bg-[var(--color-sidebar)]">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-base font-semibold text-[var(--color-text-secondary)]">History</h1>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {stats && <StatsBar stats={stats} />}

        <div className="relative mb-6">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setLoading(true);
              setSearch(e.target.value);
            }}
            placeholder="Search queries..."
            className="w-full bg-[#2f2f2f] rounded-2xl pl-10 pr-4 py-3 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none transition-colors"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-[var(--color-text-muted)] animate-spin" />
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-16 rounded-2xl bg-[var(--color-card)]">
            <BarChart3 className="w-10 h-10 text-[var(--color-text-muted)] mx-auto mb-3 opacity-30" />
            <p className="text-[var(--color-text-muted)]">
              {search ? "No results found" : "No queries yet"}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {runs.map((run) => (
                <HistoryItem key={run.id} run={run} onDelete={handleDelete} />
              ))}
            </AnimatePresence>

            {nextCursor && (
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="w-full py-3 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] rounded-2xl bg-[var(--color-card)] hover:bg-[var(--color-card-hover)] transition-all cursor-pointer"
              >
                {loadingMore ? (
                  <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                ) : (
                  "Load more"
                )}
              </button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
