"use client";

import { useState, useCallback, useEffect, useRef, Fragment } from "react";
import { motion } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Sidebar } from "@/components/sidebar";
import { AgentInput } from "@/components/agent-input";
import { StepViewer } from "@/components/step-viewer";
import { AgentResultView } from "@/components/agent-result";
import { DrivePanel } from "@/components/drive-panel";
import { AgentStateBadge } from "@/components/agent-state-badge";
import { useToast } from "@/components/toast";
import { useAuth } from "@/contexts/auth";
import { apiFetch } from "@/lib/api-client";
import type {
  AgentStep,
  AgentPlan,
  AgentResult,
  AgentState,
  TokenUsage,
} from "@/types";
import {
  Zap,
  Search,
  FileText,
  Globe,
  HardDrive,
  ArrowRight,
  Loader2,
  Sparkles,
  Brain,
  Database,
} from "lucide-react";

interface ConversationTurn {
  task: string;
  result: AgentResult;
  usage?: TokenUsage;
}

export default function Home() {
  const { authenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <Loader2 className="w-6 h-6 text-[var(--color-text-muted)] animate-spin" />
      </div>
    );
  }

  if (!authenticated) return <LandingPage />;

  return <AppShell />;
}

/* ── Landing Page ─────────────────────────────────── */

function LandingPage() {
  const { login } = useAuth();
  const { toast } = useToast();
  const [signingIn, setSigningIn] = useState<"header" | "hero" | null>(null);

  const handleSignIn = async (source: "header" | "hero") => {
    if (signingIn) return;

    setSigningIn(source);
    const result = await login();
    if (!result.ok) {
      setSigningIn(null);
      toast("error", result.error ?? "Google sign-in did not complete.");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)] flex flex-col">
      {/* Nav */}
      <header className="flex items-center justify-between px-6 md:px-10 py-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-white/10 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-semibold text-[var(--color-text)]">Archon</span>
        </div>
        <button
          onClick={() => void handleSignIn("header")}
          disabled={signingIn !== null}
          className="px-5 py-2 rounded-full bg-white text-black text-sm font-medium hover:bg-gray-200 disabled:opacity-60 transition-all cursor-pointer"
        >
          {signingIn === "header" ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Connecting...
            </span>
          ) : (
            "Sign in with Google"
          )}
        </button>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center max-w-3xl mx-auto"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-[var(--color-text-muted)] mb-8">
            <Sparkles className="w-3 h-3" />
            AI-Powered Research Agent
          </div>

          <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-[var(--color-text)] leading-[1.1] mb-6">
            Research anything,
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#b4b4b4] to-[#676767]">
              instantly.
            </span>
          </h1>

          <p className="text-lg md:text-xl text-[var(--color-text-muted)] max-w-xl mx-auto mb-10 leading-relaxed">
            Archon plans, searches the web, reads your Google Drive, and synthesizes
            comprehensive answers — all autonomously.
          </p>

          <button
            onClick={() => void handleSignIn("hero")}
            disabled={signingIn !== null}
            className="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-full bg-white text-black text-base font-semibold hover:bg-gray-200 disabled:opacity-60 transition-all cursor-pointer"
          >
            {signingIn === "hero" ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                Get started
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </motion.div>

        {/* Features */}
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-20 max-w-3xl w-full"
        >
          {[
            {
              icon: Globe,
              title: "Web Search",
              desc: "Searches the internet in real time to find the latest information.",
            },
            {
              icon: HardDrive,
              title: "Google Drive",
              desc: "Connect your Drive to search and analyze your personal documents.",
            },
            {
              icon: Brain,
              title: "Autonomous Agent",
              desc: "Plans multi-step research, adapts on the fly, and cites every source.",
            },
          ].map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-colors"
            >
              <div className="w-9 h-9 rounded-xl bg-white/[0.06] flex items-center justify-center mb-3">
                <Icon className="w-4.5 h-4.5 text-[var(--color-text-secondary)]" />
              </div>
              <h3 className="text-sm font-medium text-[var(--color-text)] mb-1">{title}</h3>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">{desc}</p>
            </div>
          ))}
        </motion.div>

        {/* How it works */}
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: "easeOut" }}
          className="mt-20 max-w-2xl w-full"
        >
          <p className="text-xs text-[var(--color-text-muted)] text-center mb-6 uppercase tracking-wider">
            How it works
          </p>
          <div className="flex flex-col md:flex-row items-start md:items-center gap-3 md:gap-0">
            {[
              { icon: Search, label: "Ask a question" },
              { icon: FileText, label: "Agent plans steps" },
              { icon: Database, label: "Searches & reads" },
              { icon: Sparkles, label: "Synthesizes answer" },
            ].map(({ icon: Icon, label }, i) => (
              <Fragment key={label}>
                <div className="flex items-center gap-3 flex-1">
                  <div className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center shrink-0">
                    <Icon className="w-3.5 h-3.5 text-[var(--color-text-secondary)]" />
                  </div>
                  <span className="text-sm text-[var(--color-text-secondary)]">{label}</span>
                </div>
                {i < 3 && (
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--color-text-muted)]/30 shrink-0 mx-2 hidden md:block" />
                )}
              </Fragment>
            ))}
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="text-center py-6 px-4">
        <p className="text-xs text-[var(--color-text-muted)]">
          Built with Next.js, OpenAI, and Google APIs
        </p>
      </footer>
    </div>
  );
}

/* ── App Shell (authenticated) ─────────────────────── */

function AppShell() {
  const { toast } = useToast();
  const { logout, refresh } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [driveOpen, setDriveOpen] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [thinking, setThinking] = useState<string | null>(null);
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [hasStarted, setHasStarted] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [previousTurns, setPreviousTurns] = useState<ConversationTurn[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps, thinking, streamedAnswer, result, previousTurns]);

  const handleNewConversation = useCallback(() => {
    setConversationId(null);
    setPreviousTurns([]);
    setResult(null);
    setUsage(null);
    setStreamedAnswer("");
    setSteps([]);
    setPlan(null);
    setThinking(null);
    setHasStarted(false);
    setAgentState("idle");
  }, []);

  const lastTaskRef = useRef<string>("");

  const handleSubmit = useCallback(
    async (task: string, maxSteps: number) => {
      if (result && lastTaskRef.current) {
        setPreviousTurns((prev) => [
          ...prev,
          { task: lastTaskRef.current, result, usage: usage ?? undefined },
        ]);
      }

      lastTaskRef.current = task;
      setIsRunning(true);
      setHasStarted(true);
      setThinking("Initializing research agent...");
      setPlan(null);
      setSteps([]);
      setResult(null);
      setUsage(null);
      setStreamedAnswer("");
      setAgentState("planning");

      try {
        const res = await apiFetch("/api/agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task,
            maxSteps,
            ...(conversationId ? { conversationId } : {}),
          }),
        });

        if (!res.ok) {
          if (res.status === 401) {
            refresh();
            setIsRunning(false);
            setAgentState("error");
            return;
          }
          const data = await res
            .json()
            .catch(() => ({ error: `HTTP ${res.status}` }));
          toast("error", data.error ?? "Request failed");
          setIsRunning(false);
          setAgentState("error");
          return;
        }

        setCurrentRunId(res.headers.get("X-Run-Id"));

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(part.slice(6));

              switch (event.type) {
                case "conversation_id":
                  setConversationId(event.conversationId);
                  break;
                case "state_change":
                  setAgentState(event.state);
                  break;
                case "thinking":
                  setThinking(event.content);
                  break;
                case "plan":
                  setPlan(event.plan);
                  setThinking(null);
                  break;
                case "step_start":
                  setThinking(null);
                  setSteps((prev) => [...prev, event.step as AgentStep]);
                  break;
                case "step_complete":
                  setSteps((prev) =>
                    prev.map((s) =>
                      s.id === event.step.id ? event.step : s
                    )
                  );
                  break;
                case "answer_chunk":
                  setThinking(null);
                  setStreamedAnswer((prev) => prev + event.content);
                  break;
                case "complete":
                  setStreamedAnswer("");
                  setResult(event.result);
                  setUsage(event.usage ?? null);
                  setThinking(null);
                  setAgentState("completed");
                  break;
                case "error":
                  setResult({
                    answer: `Error: ${event.error}`,
                    citations: [],
                    steps: [],
                    totalSteps: 0,
                    durationMs: 0,
                    status: "error",
                  });
                  setThinking(null);
                  setAgentState("error");
                  toast("error", event.error);
                  break;
              }
            } catch {
              /* skip malformed JSON */
            }
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        toast("error", `Connection failed: ${msg}`);
        setResult({
          answer: `Failed to connect: ${msg}`,
          citations: [],
          steps: [],
          totalSteps: 0,
          durationMs: 0,
          status: "error",
        });
        setAgentState("error");
      } finally {
        setIsRunning(false);
        setThinking(null);
      }
    },
    [toast, conversationId, result, usage, refresh]
  );

  const showActivity = plan || steps.length > 0 || thinking;

  return (
    <div className="h-screen flex overflow-hidden bg-[var(--color-bg)]">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={handleNewConversation}
        onLogout={logout}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full">
        <Navbar
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          driveOpen={driveOpen}
          onToggleDrive={() => setDriveOpen(!driveOpen)}
        />

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto">
          {!hasStarted ? (
            <IdlePrompt />
          ) : (
            <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-6">
              {previousTurns.map((turn, i) => (
                <Fragment key={i}>
                  <UserMessage content={turn.task} />
                  <AssistantMessage>
                    <AgentResultView
                      result={turn.result}
                      usage={turn.usage}
                    />
                  </AssistantMessage>
                </Fragment>
              ))}

              {lastTaskRef.current && (
                <>
                  <UserMessage content={lastTaskRef.current} />

                  <AssistantMessage>
                    {isRunning && (
                      <div className="mb-3">
                        <AgentStateBadge state={agentState} />
                      </div>
                    )}

                    {showActivity && (
                      <div className="mb-4">
                        <StepViewer steps={steps} plan={plan} thinking={thinking} />
                      </div>
                    )}

                    {streamedAnswer && isRunning && (
                      <div className="prose max-w-none">
                        <div
                          dangerouslySetInnerHTML={{
                            __html: renderSimpleMarkdown(streamedAnswer),
                          }}
                        />
                        <span className="inline-block w-1.5 h-5 bg-[var(--color-text-muted)] animate-pulse ml-0.5 align-text-bottom rounded-sm" />
                      </div>
                    )}

                    {result && !isRunning && (
                      <AgentResultView
                        result={result}
                        usage={usage ?? undefined}
                        runId={currentRunId ?? undefined}
                      />
                    )}

                    {isRunning && !streamedAnswer && !result && !showActivity && (
                      <div className="flex items-center gap-2">
                        <div className="flex gap-1">
                          {[0, 1, 2].map((i) => (
                            <motion.div
                              key={i}
                              className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)]"
                              animate={{ opacity: [0.3, 1, 0.3] }}
                              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </AssistantMessage>
                </>
              )}

              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="shrink-0 pb-4 pt-2 print:hidden">
          <div className="max-w-3xl mx-auto px-4 md:px-6">
            <AgentInput
              onSubmit={handleSubmit}
              isRunning={isRunning}
              placeholder={
                previousTurns.length > 0
                  ? "Ask a follow-up..."
                  : "Ask anything..."
              }
            />
            <p className="text-[11px] text-[var(--color-text-muted)] text-center mt-2">
              Archon can make mistakes. Verify important information.
            </p>
          </div>
        </div>
      </div>

      <DrivePanel isOpen={driveOpen} onClose={() => setDriveOpen(false)} />
    </div>
  );
}

/* ── Inline Components ─────────────────────────────────── */

function UserMessage({ content }: { content: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-end"
    >
      <div className="max-w-[80%]">
        <div className="user-bubble px-4 py-3">
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    </motion.div>
  );
}

function AssistantMessage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-3"
    >
      <div className="w-7 h-7 rounded-full bg-[#2a2a2a] flex items-center justify-center shrink-0 mt-1">
        <Zap className="w-3.5 h-3.5 text-[var(--color-text-secondary)]" />
      </div>
      <div className="flex-1 min-w-0 pt-0.5">
        {children}
      </div>
    </motion.div>
  );
}

function IdlePrompt() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 min-h-[calc(100vh-8rem)]">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center"
      >
        <h1 className="text-3xl font-semibold tracking-tight mb-1 text-[var(--color-text)]">
          What are you working on?
        </h1>
        <p className="text-[var(--color-text-muted)] text-base">
          Research anything with AI-powered web search and document analysis.
        </p>
      </motion.div>
    </div>
  );
}

function renderSimpleMarkdown(text: string): string {
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
    .replace(/^\d+\. (.*$)/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`);
  html = html.replace(/\n\n/g, "</p><p>");
  return `<p>${html}</p>`;
}
