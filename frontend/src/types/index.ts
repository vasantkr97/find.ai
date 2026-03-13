import { z } from "zod";

// ── Tool Types ──────────────────────────────────────────────────────────

export const toolResultSchema = z.object({
  success: z.boolean(),
  data: z.unknown(),
  error: z.string().optional(),
});
export type ToolResult = z.infer<typeof toolResultSchema>;

export const parameterDefSchema = z.object({
  type: z.string(),
  description: z.string(),
  required: z.boolean().optional(),
});
export type ParameterDef = z.infer<typeof parameterDefSchema>;

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, ParameterDef>;
  execute: (args: Record<string, unknown>) => Promise<ToolResult>;
}

// ── Token Usage ─────────────────────────────────────────────────────────

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimatedCost: number;
}

export function emptyUsage(): TokenUsage {
  return { promptTokens: 0, completionTokens: 0, totalTokens: 0, estimatedCost: 0 };
}

const GPT4O_MINI_INPUT_COST = 0.15 / 1_000_000;
const GPT4O_MINI_OUTPUT_COST = 0.60 / 1_000_000;

export function addUsage(acc: TokenUsage, prompt: number, completion: number): TokenUsage {
  const promptTokens = acc.promptTokens + prompt;
  const completionTokens = acc.completionTokens + completion;
  return {
    promptTokens,
    completionTokens,
    totalTokens: promptTokens + completionTokens,
    estimatedCost:
      promptTokens * GPT4O_MINI_INPUT_COST +
      completionTokens * GPT4O_MINI_OUTPUT_COST,
  };
}

// ── Agent Types ─────────────────────────────────────────────────────────

export const citationSchema = z.object({
  title: z.string(),
  url: z.string().optional(),
  source: z.string(),
  snippet: z.string().optional(),
});
export type Citation = z.infer<typeof citationSchema>;

export const planStepSchema = z.object({
  description: z.string(),
  tool: z.string().nullable(),
  reasoning: z.string(),
});
export type PlanStep = z.infer<typeof planStepSchema>;

export const agentPlanSchema = z.object({
  analysis: z.string(),
  steps: z.array(planStepSchema),
});
export type AgentPlan = z.infer<typeof agentPlanSchema>;

export const agentStepSchema = z.object({
  id: z.string(),
  index: z.number().int().min(0),
  reasoning: z.string(),
  action: z
    .object({
      tool: z.string(),
      args: z.record(z.string(), z.unknown()),
    })
    .nullable(),
  result: toolResultSchema.nullable(),
  timestamp: z.number(),
  durationMs: z.number().optional(),
});
export type AgentStep = z.infer<typeof agentStepSchema>;

export const agentStatusSchema = z.enum(["completed", "step_limit", "error", "aborted"]);
export type AgentStatus = z.infer<typeof agentStatusSchema>;

export const agentResultSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema),
  steps: z.array(agentStepSchema),
  totalSteps: z.number().int().min(0),
  durationMs: z.number().min(0),
  status: agentStatusSchema,
});
export type AgentResult = z.infer<typeof agentResultSchema>;

export interface AgentOptions {
  task: string;
  maxSteps: number;
  signal?: AbortSignal;
  runId?: string;
  conversationId?: string;
  previousTurns?: Array<{ task: string; answer: string }>;
}

// ── Agent State Machine ─────────────────────────────────────────────────

export const agentStateSchema = z.enum([
  "idle",
  "planning",
  "deciding",
  "executing",
  "synthesizing",
  "completed",
  "error",
  "aborted",
]);
export type AgentState = z.infer<typeof agentStateSchema>;

// ── Agent Events ────────────────────────────────────────────────────────

export type AgentEvent =
  | { type: "state_change"; state: AgentState }
  | { type: "thinking"; content: string }
  | { type: "plan"; plan: AgentPlan }
  | { type: "step_start"; step: AgentStep }
  | { type: "step_complete"; step: AgentStep }
  | { type: "answer_chunk"; content: string }
  | { type: "complete"; result: AgentResult; usage: TokenUsage }
  | { type: "error"; error: string };

// ── LLM Types ───────────────────────────────────────────────────────────

// Coerce LLM "answer" field: accept string or object (e.g. { text } or { content }) and normalize to string
const answerStringSchema = z.preprocess(
  (val) => {
    if (typeof val === "string") return val;
    if (val != null && typeof val === "object" && !Array.isArray(val)) {
      const o = val as Record<string, unknown>;
      if (typeof o.text === "string") return o.text;
      if (typeof o.content === "string") return o.content;
      return JSON.stringify(o);
    }
    return String(val ?? "");
  },
  z.string()
);

export const nextActionSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("tool_call"),
    reasoning: z.string(),
    tool: z.string(),
    args: z.record(z.string(), z.unknown()).optional().default({}),
  }),
  z.object({
    type: z.literal("complete"),
    reasoning: z.string(),
    answer: answerStringSchema,
  }),
]);
export type NextAction = z.infer<typeof nextActionSchema>;

export const synthesisResultSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema),
});
export type SynthesisResult = z.infer<typeof synthesisResultSchema>;

// ── Drive Types ─────────────────────────────────────────────────────────

export const driveFileSchema = z.object({
  id: z.string(),
  name: z.string(),
  mimeType: z.string(),
  modifiedTime: z.string(),
  size: z.string().optional(),
});
export type DriveFile = z.infer<typeof driveFileSchema>;

export interface IngestProgress {
  total: number;
  processed: number;
  current?: string;
  errors: { file: string; error: string }[];
}

// ── Vector Types ────────────────────────────────────────────────────────

export interface VectorDocument {
  id: string;
  content: string;
  embedding: number[];
  metadata: Record<string, string>;
  createdAt: number;
}

export interface VectorSearchResult {
  document: VectorDocument;
  score: number;
}

export interface VectorSearchOptions {
  topK?: number;
  threshold?: number;
  metadataFilter?: Record<string, string>;
}

export interface VectorStoreStats {
  totalDocuments: number;
  sources: Record<string, number>;
}

// ── API Types ───────────────────────────────────────────────────────────

export const agentRequestSchema = z.object({
  task: z.string().min(1).max(2000),
  maxSteps: z.number().int().min(1).max(30).default(10),
  userId: z.string().optional(),
  conversationId: z.string().optional(),
});
export type AgentRequest = z.infer<typeof agentRequestSchema>;

export const ingestRequestSchema = z.object({
  incremental: z.boolean().default(true),
});
export type IngestRequest = z.infer<typeof ingestRequestSchema>;
