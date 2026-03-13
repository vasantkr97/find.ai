import { notFound } from "next/navigation";
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  Footprints,
  FileText,
  Zap,
} from "lucide-react";

interface ShareStep {
  id: string;
  index: number;
  reasoning: string;
  tool: string | null;
}

interface ShareRun {
  id: string;
  task: string;
  answer: string;
  status: string;
  totalSteps: number;
  durationMs: number;
  createdAt: string;
  steps: ShareStep[];
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

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
  html = html
    .replace(/<p><h([123])>/g, "<h$1>")
    .replace(/<\/h([123])><\/p>/g, "</h$1>");
  html = html
    .replace(/<p><ul>/g, "<ul>")
    .replace(/<\/ul><\/p>/g, "</ul>");

  return html;
}

export default async function SharePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const backendBase = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8081").replace(/\/$/, "");
  const res = await fetch(`${backendBase}/api/share/${id}`, { cache: "no-store" });
  if (!res.ok) notFound();
  const run = (await res.json()) as ShareRun;

  const toolSources: Record<string, string> = {
    web_search: "Web",
    web_scrape: "Webpage",
    drive_search: "Drive",
    vector_search: "Documents",
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <nav className="border-b border-zinc-800/50 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight">Archon</span>
          <span className="text-xs text-zinc-500 font-medium ml-1">Shared Result</span>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <p className="text-sm text-zinc-500 mb-2">Research Query</p>
          <h1 className="text-xl font-semibold text-zinc-100">{run.task}</h1>
        </div>

        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span className="flex items-center gap-1">
            {run.status === "completed" ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            )}
            {run.status}
          </span>
          <span className="flex items-center gap-1">
            <Footprints className="w-3.5 h-3.5" />
            {run.totalSteps} steps
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {formatDuration(run.durationMs)}
          </span>
            <span>{new Date(run.createdAt).toLocaleDateString()}</span>
        </div>

        {run.steps.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Research Steps
            </h2>
            <div className="space-y-1.5">
              {run.steps.map((step) => (
                <div
                  key={step.id}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg border border-zinc-800/50 bg-zinc-900/30 text-sm"
                >
                  <span className="text-xs font-mono text-zinc-600 w-5 text-right shrink-0">
                    {step.index + 1}
                  </span>
                  <span className="text-zinc-300 truncate flex-1">{step.reasoning}</span>
                  {step.tool && (
                    <span className="text-xs text-zinc-500 shrink-0">
                      {toolSources[step.tool] ?? step.tool}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="border border-zinc-800 rounded-xl bg-zinc-900/30 p-5">
          <div
            className="prose max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(run.answer) }}
          />
        </div>

        <div className="text-center pt-4 border-t border-zinc-800/50">
          <p className="text-xs text-zinc-600">
            Generated by Archon AI Research Agent
          </p>
        </div>
      </main>
    </div>
  );
}
