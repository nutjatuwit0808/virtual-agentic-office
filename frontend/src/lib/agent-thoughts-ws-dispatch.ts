import type { Dispatch, SetStateAction } from "react";

import type { AgentRole, AgentStatus } from "@/lib/agents";
import { isAgentRole } from "@/lib/agents";
import type {
  EscalationState,
  LlmTokenUsage,
  ThoughtEvent,
} from "@/lib/agent-log-types";

export const AGENT_LOG_MAX_LINES = 300;

const AGENT_ROLES: AgentRole[] = [
  "pm",
  "researcher",
  "developer",
  "writer",
  "qa",
];

function emptyUsage(): LlmTokenUsage {
  return { input: 0, output: 0, total: 0 };
}

function emptyUsageByAgent(): Record<AgentRole, LlmTokenUsage> {
  return {
    pm: emptyUsage(),
    researcher: emptyUsage(),
    developer: emptyUsage(),
    writer: emptyUsage(),
    qa: emptyUsage(),
  };
}

function parseUsageRow(raw: unknown): LlmTokenUsage | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const input = Number(o.input_tokens ?? o.input ?? 0);
  const output = Number(o.output_tokens ?? o.output ?? 0);
  let total = Number(o.total_tokens ?? o.total ?? NaN);
  if (!Number.isFinite(total)) {
    total = input + output;
  }
  if (
    !Number.isFinite(input) ||
    !Number.isFinite(output) ||
    !Number.isFinite(total)
  ) {
    return null;
  }
  return { input, output, total };
}

function mergeUsageFromServer(
  raw: unknown
): Record<AgentRole, LlmTokenUsage> | null {
  if (!raw || typeof raw !== "object") return null;
  const next = emptyUsageByAgent();
  const o = raw as Record<string, unknown>;
  for (const [k, v] of Object.entries(o)) {
    if (!isAgentRole(k)) continue;
    const row = parseUsageRow(v);
    if (row) next[k] = row;
  }
  return next;
}

function isAgentStatus(v: unknown): v is AgentStatus {
  return v === "idle" || v === "thinking" || v === "working";
}

function mergeAgentStatus(
  prev: Record<AgentRole, AgentStatus>,
  raw: unknown
): Record<AgentRole, AgentStatus> {
  if (!raw || typeof raw !== "object") return prev;
  const next = { ...prev };
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (isAgentRole(k) && isAgentStatus(v)) {
      next[k] = v;
    }
  }
  return next;
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

export type AgentThoughtsWsDeps = {
  appendGlobal: (line: string) => void;
  appendAgentLine: (role: AgentRole, line: string) => void;
  setThoughts: Dispatch<SetStateAction<ThoughtEvent[]>>;
  setStatusByAgent: Dispatch<SetStateAction<Record<AgentRole, AgentStatus>>>;
  setLoopCounter: Dispatch<SetStateAction<number>>;
  setEscalation: Dispatch<SetStateAction<EscalationState | null>>;
  setUsageByAgent: Dispatch<SetStateAction<Record<AgentRole, LlmTokenUsage>>>;
};

/**
 * Applies one WebSocket JSON payload from `/ws/agent-thoughts`.
 * Side effects only; swallows malformed payloads at the caller.
 */
export function dispatchAgentThoughtsMessage(
  raw: Record<string, unknown>,
  deps: AgentThoughtsWsDeps
): void {
  const {
    appendGlobal,
    appendAgentLine,
    setThoughts,
    setStatusByAgent,
    setLoopCounter,
    setEscalation,
    setUsageByAgent,
  } = deps;

  const ts =
    typeof raw.ts === "number" ? raw.ts : Math.floor(Date.now() / 1000);
  const type =
    typeof raw.type === "string"
      ? raw.type
      : raw.agent && raw.thought
        ? "thought"
        : "";

  if (type === "thought" || (!raw.type && raw.agent && raw.thought)) {
    const agent = String(raw.agent ?? "");
    const thought = String(raw.thought ?? "");
    setThoughts((prev) =>
      [...prev, { agent, thought, ts }].slice(-AGENT_LOG_MAX_LINES)
    );
    appendGlobal(`${formatTime(ts)} [thought] ${agent}: ${thought}`);
    if (isAgentRole(agent.toLowerCase())) {
      const role = agent.toLowerCase() as AgentRole;
      appendAgentLine(role, `${formatTime(ts)} ${thought}`);
      setStatusByAgent((s) => ({ ...s, [role]: "working" }));
    }
    return;
  }

  if (type === "terminal") {
    const agent = String(raw.agent ?? "");
    const line = String(raw.line ?? "");
    const stream = String(raw.stream ?? "stdout");
    if (!line) return;
    const lineLabel = `${formatTime(ts)} [${stream}] ${line}`;
    appendGlobal(lineLabel);
    if (isAgentRole(agent.toLowerCase())) {
      const role = agent.toLowerCase() as AgentRole;
      appendAgentLine(role, lineLabel);
      setStatusByAgent((s) => ({ ...s, [role]: "working" }));
    }
    return;
  }

  if (type === "node_start") {
    const node = String(raw.node ?? "");
    const agentId = String(raw.agent ?? "");
    const line = `${formatTime(ts)} [node] ${node} start`;
    appendGlobal(line);
    if (isAgentRole(agentId)) {
      appendAgentLine(agentId, line);
      setStatusByAgent((s) => ({ ...s, [agentId]: "working" }));
    }
    return;
  }

  if (type === "node_end") {
    const node = String(raw.node ?? "");
    const agentId = String(raw.agent ?? "");
    const line = `${formatTime(ts)} [node] ${node} end`;
    appendGlobal(line);
    if (isAgentRole(agentId)) {
      appendAgentLine(agentId, line);
    }
    if (raw.agent_status) {
      setStatusByAgent((s) => mergeAgentStatus(s, raw.agent_status));
    }
    if (typeof raw.loop_counter === "number") {
      const n = raw.loop_counter;
      setLoopCounter((c) => Math.max(c, n));
    }
    return;
  }

  if (type === "tool_start") {
    const tool = String(raw.tool ?? "tool");
    const detail = String(raw.detail ?? "");
    const agentId = String(raw.agent ?? "");
    const line = `${formatTime(ts)} [tool] ${tool} ${detail}`;
    appendGlobal(line);
    if (agentId && isAgentRole(agentId)) {
      appendAgentLine(agentId as AgentRole, line);
    }
    return;
  }

  if (type === "tool_end") {
    const tool = String(raw.tool ?? "tool");
    const detail = String(raw.detail ?? "");
    const agentId = String(raw.agent ?? "");
    const line = `${formatTime(ts)} [tool/end] ${tool} ${detail}`;
    appendGlobal(line);
    if (agentId && isAgentRole(agentId)) {
      appendAgentLine(agentId as AgentRole, line);
    }
    return;
  }

  if (type === "token") {
    const text = String(raw.text ?? "");
    const agentId = String(raw.agent ?? "");
    if (!text) return;
    const line = `${formatTime(ts)} [stream] ${text}`;
    appendGlobal(line);
    if (agentId && isAgentRole(agentId)) {
      appendAgentLine(agentId as AgentRole, line);
      setStatusByAgent((s) => ({ ...s, [agentId]: "working" }));
    }
    return;
  }

  if (type === "llm_usage") {
    const agentId = String(raw.agent ?? "").toLowerCase();
    if (!isAgentRole(agentId)) return;
    const role = agentId as AgentRole;
    const input = Number(raw.input_tokens ?? 0);
    const output = Number(raw.output_tokens ?? 0);
    const total = Number(
      raw.total_tokens ??
        (Number.isFinite(input) && Number.isFinite(output) ? input + output : 0)
    );
    if (
      !Number.isFinite(input) ||
      !Number.isFinite(output) ||
      !Number.isFinite(total)
    ) {
      return;
    }
    setUsageByAgent((prev) => ({
      ...prev,
      [role]: {
        input: prev[role].input + input,
        output: prev[role].output + output,
        total: prev[role].total + total,
      },
    }));
    appendGlobal(
      `${formatTime(ts)} [llm] +${total} tok (${agentId} Δin ${input} · Δout ${output})`
    );
    return;
  }

  if (type === "graph_end") {
    if (raw.agent_status) {
      setStatusByAgent((s) => mergeAgentStatus(s, raw.agent_status));
    }
    const phase = String(raw.current_phase ?? "");
    const merged = mergeUsageFromServer(raw.usage_by_agent);
    if (merged) {
      setUsageByAgent(merged);
    }
    const totalsRow = parseUsageRow(raw.usage_totals);
    appendGlobal(
      `${formatTime(ts)} [graph] complete${phase ? ` phase=${phase}` : ""}` +
        (totalsRow
          ? ` · API tokens Σ ${totalsRow.total} (in ${totalsRow.input} · out ${totalsRow.output})`
          : "")
    );
    if (typeof raw.loop_counter === "number") {
      const n = raw.loop_counter;
      setLoopCounter((c) => Math.max(c, n));
    }
    const rs = String(raw.run_status ?? "");
    if (rs.startsWith("RESOLVED_") || phase === "resolved") {
      setEscalation(null);
    }
  }

  if (type === "graph_loop_lock") {
    const msg = String(raw.message ?? "Workflow locked (recursion limit).");
    appendGlobal(`${formatTime(ts)} [graph] LOCKED_BY_LOOP — ${msg}`);
  }

  if (type === "escalation_wait") {
    const sid = String(raw.thread_id ?? "");
    const sum = String(raw.summary ?? "").slice(0, 280);
    appendGlobal(
      `${formatTime(ts)} [Office Manager] Paused — awaiting your decision (thread ${sid.slice(0, 8)}…). ${sum}${sum.length >= 280 ? "…" : ""}`
    );
    const rawOpts = raw.options;
    const options: EscalationState["options"] = [];
    if (Array.isArray(rawOpts)) {
      for (const o of rawOpts) {
        if (!o || typeof o !== "object") continue;
        const ob = o as Record<string, unknown>;
        const id = String(ob.id ?? "");
        if (!id) continue;
        options.push({
          id,
          label: String(ob.label ?? id),
          description: String(ob.description ?? ""),
        });
      }
    }
    setEscalation({
      threadId: sid,
      summary: String(raw.summary ?? ""),
      options,
    });
  }
}

export function computeUsageTotals(
  usageByAgent: Record<AgentRole, LlmTokenUsage>
): LlmTokenUsage {
  return AGENT_ROLES.reduce<LlmTokenUsage>(
    (acc, role) => ({
      input: acc.input + usageByAgent[role].input,
      output: acc.output + usageByAgent[role].output,
      total: acc.total + usageByAgent[role].total,
    }),
    emptyUsage()
  );
}
