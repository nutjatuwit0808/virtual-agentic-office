"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getWsBaseUrl } from "@/lib/env";
import type { AgentRole } from "@/lib/agents";

export type ThoughtEvent = {
  agent: string;
  thought: string;
  ts: number;
};

export function useAgentThoughtsWebSocket() {
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const clear = useCallback(() => setThoughts([]), []);

  useEffect(() => {
    const base = getWsBaseUrl().replace(/\/$/, "");
    const url = `${base}/ws/agent-thoughts`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as ThoughtEvent;
        if (data.agent && data.thought) {
          setThoughts((prev) => [...prev, data].slice(-300));
        }
      } catch {
        /* ignore */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, []);

  const thoughtsForAgent = useCallback(
    (role: AgentRole) =>
      thoughts.filter((t) => t.agent.toLowerCase() === role),
    [thoughts]
  );

  return { thoughts, thoughtsForAgent, connected, clear };
}
