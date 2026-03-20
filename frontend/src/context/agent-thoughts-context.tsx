"use client";

import { createContext, useContext, type ReactNode } from "react";

import {
  useAgentThoughtsWebSocket,
  type ThoughtEvent,
} from "@/hooks/useAgentThoughtsWebSocket";
import type { AgentRole } from "@/lib/agents";

export type AgentThoughtsContextValue = {
  thoughts: ThoughtEvent[];
  thoughtsForAgent: (role: AgentRole) => ThoughtEvent[];
  connected: boolean;
  clear: () => void;
};

const AgentThoughtsContext = createContext<AgentThoughtsContextValue | null>(
  null
);

export function AgentThoughtsProvider({ children }: { children: ReactNode }) {
  const value = useAgentThoughtsWebSocket();
  return (
    <AgentThoughtsContext.Provider value={value}>
      {children}
    </AgentThoughtsContext.Provider>
  );
}

export function useAgentThoughts(): AgentThoughtsContextValue {
  const ctx = useContext(AgentThoughtsContext);
  if (!ctx) {
    throw new Error("useAgentThoughts must be used within AgentThoughtsProvider");
  }
  return ctx;
}
