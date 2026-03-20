"use client";

import { createContext, useContext, type ReactNode } from "react";

import {
  useAgentLogWebSocket,
  type EscalationState,
  type LlmTokenUsage,
  type ThoughtEvent,
} from "@/hooks/useAgentLog";
import type { AgentRole, AgentStatus } from "@/lib/agents";

export type AgentLogContextValue = {
  thoughts: ThoughtEvent[];
  thoughtsForAgent: (role: AgentRole) => ThoughtEvent[];
  logForAgent: (role: AgentRole) => string[];
  globalLog: string[];
  statusByAgent: Record<AgentRole, AgentStatus>;
  connected: boolean;
  clear: () => void;
  loopCounter: number;
  escalation: EscalationState | null;
  applyEscalationFromApi: (payload: EscalationState | null) => void;
  beginGraphRun: () => void;
  usageByAgent: Record<AgentRole, LlmTokenUsage>;
  usageTotals: LlmTokenUsage;
};

const AgentLogContext = createContext<AgentLogContextValue | null>(null);

export function AgentThoughtsProvider({ children }: { children: ReactNode }) {
  const value = useAgentLogWebSocket();
  return (
    <AgentLogContext.Provider value={value}>{children}</AgentLogContext.Provider>
  );
}

export function useAgentLog(): AgentLogContextValue {
  const ctx = useContext(AgentLogContext);
  if (!ctx) {
    throw new Error("useAgentLog must be used within AgentThoughtsProvider");
  }
  return ctx;
}

/** @deprecated Use useAgentLog() */
export function useAgentThoughts(): AgentLogContextValue {
  return useAgentLog();
}
