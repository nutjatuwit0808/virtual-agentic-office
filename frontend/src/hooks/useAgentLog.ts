"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AGENT_LOG_MAX_LINES,
  computeUsageTotals,
  dispatchAgentThoughtsMessage,
  type AgentThoughtsWsDeps,
} from "@/lib/agent-thoughts-ws-dispatch";
import type {
  EscalationState,
  LlmTokenUsage,
  ThoughtEvent,
} from "@/lib/agent-log-types";
import { getWsBaseUrl } from "@/lib/env";
import {
  type AgentRole,
  type AgentStatus,
} from "@/lib/agents";

export type { EscalationState, LlmTokenUsage, ThoughtEvent };

const idleStatuses = (): Record<AgentRole, AgentStatus> => ({
  pm: "idle",
  researcher: "idle",
  developer: "idle",
  writer: "idle",
  qa: "idle",
});

const emptyAgentLines = (): Record<AgentRole, string[]> => ({
  pm: [],
  researcher: [],
  developer: [],
  writer: [],
  qa: [],
});

const emptyUsageByAgent = (): Record<AgentRole, LlmTokenUsage> => ({
  pm: { input: 0, output: 0, total: 0 },
  researcher: { input: 0, output: 0, total: 0 },
  developer: { input: 0, output: 0, total: 0 },
  writer: { input: 0, output: 0, total: 0 },
  qa: { input: 0, output: 0, total: 0 },
});

/** WebSocket subscription; prefer `useAgentLog` from `@/context/agent-thoughts-context`. */
export function useAgentLogWebSocket() {
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [statusByAgent, setStatusByAgent] =
    useState<Record<AgentRole, AgentStatus>>(idleStatuses);
  const [linesByAgent, setLinesByAgent] = useState<Record<AgentRole, string[]>>(
    emptyAgentLines
  );
  const [globalLog, setGlobalLog] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [loopCounter, setLoopCounter] = useState(0);
  const [escalation, setEscalation] = useState<EscalationState | null>(null);
  const [usageByAgent, setUsageByAgent] =
    useState<Record<AgentRole, LlmTokenUsage>>(emptyUsageByAgent);
  const wsRef = useRef<WebSocket | null>(null);

  const usageTotals = useMemo(
    () => computeUsageTotals(usageByAgent),
    [usageByAgent]
  );

  const appendGlobal = useCallback((line: string) => {
    setGlobalLog((prev) => [...prev, line].slice(-AGENT_LOG_MAX_LINES));
  }, []);

  const appendAgentLine = useCallback((role: AgentRole, line: string) => {
    setLinesByAgent((prev) => ({
      ...prev,
      [role]: [...(prev[role] ?? []), line].slice(-AGENT_LOG_MAX_LINES),
    }));
  }, []);

  const clear = useCallback(() => {
    setThoughts([]);
    setStatusByAgent(idleStatuses());
    setLinesByAgent(emptyAgentLines());
    setGlobalLog([]);
    setLoopCounter(0);
    setEscalation(null);
    setUsageByAgent(emptyUsageByAgent());
  }, []);

  const applyEscalationFromApi = useCallback((payload: EscalationState | null) => {
    setEscalation(payload);
  }, []);

  const beginGraphRun = useCallback(() => {
    setLoopCounter(0);
    setEscalation(null);
    setUsageByAgent(emptyUsageByAgent());
  }, []);

  useEffect(() => {
    const base = getWsBaseUrl().replace(/\/$/, "");
    const url = `${base}/ws/agent-thoughts`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    const deps: AgentThoughtsWsDeps = {
      appendGlobal,
      appendAgentLine,
      setThoughts,
      setStatusByAgent,
      setLoopCounter,
      setEscalation,
      setUsageByAgent,
    };

    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data as string) as Record<
          string,
          unknown
        >;
        dispatchAgentThoughtsMessage(raw, deps);
      } catch {
        /* ignore malformed */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [appendAgentLine, appendGlobal]);

  const thoughtsForAgent = useCallback(
    (role: AgentRole) =>
      thoughts.filter((t) => t.agent.toLowerCase() === role),
    [thoughts]
  );

  const logForAgent = useCallback(
    (role: AgentRole) => linesByAgent[role] ?? [],
    [linesByAgent]
  );

  return {
    connected,
    clear,
    statusByAgent,
    thoughts,
    thoughtsForAgent,
    logForAgent,
    globalLog,
    loopCounter,
    escalation,
    applyEscalationFromApi,
    beginGraphRun,
    usageByAgent,
    usageTotals,
  };
}
