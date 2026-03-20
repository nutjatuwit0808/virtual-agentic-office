"use client";

import { useMemo } from "react";

import type { AgentDefinition } from "@/lib/agents";
import { useAgentThoughts } from "@/context/agent-thoughts-context";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

const mockInterAgentChat = [
  { from: "pm", to: "researcher", text: "Can you summarize competitor positioning?" },
  { from: "researcher", to: "pm", text: "Draft summary is in shared artifacts." },
  { from: "dev", to: "qa", text: "Pushing build candidate for smoke tests." },
];

export function AgentDeepDivePage({ agent }: { agent: AgentDefinition }) {
  const { thoughtsForAgent, connected } = useAgentThoughts();
  const monologue = useMemo(
    () => thoughtsForAgent(agent.id),
    [thoughtsForAgent, agent.id]
  );
  const chatForAgent = mockInterAgentChat.filter(
    (m) => m.from === agent.id || m.to === agent.id
  );

  return (
    <div className="grid max-w-4xl gap-6">
      <div className="flex items-center gap-2">
        <Badge variant={connected ? "default" : "secondary"}>
          {connected ? "Live" : "Offline"}
        </Badge>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Internal monologue</CardTitle>
          <CardDescription>
            Streamed thoughts for this agent from the WebSocket feed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-64 rounded-md border bg-muted/20 p-4">
            {monologue.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No thoughts yet. Run the workflow from the dashboard.
              </p>
            ) : (
              <ul className="space-y-3 text-sm">
                {monologue.map((t, i) => (
                  <li key={`${t.ts}-${i}`}>
                    <span className="text-muted-foreground">
                      {new Date(t.ts * 1000).toLocaleTimeString()}
                    </span>
                    <p className="mt-0.5 leading-relaxed">{t.thought}</p>
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
      <Separator />
      <Card>
        <CardHeader>
          <CardTitle>Chat with other agents</CardTitle>
          <CardDescription>
            Illustrative messages (replace with LangGraph message history).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            {chatForAgent.map((m, i) => (
              <li key={i}>
                <span className="font-medium">{m.from}</span>
                <span className="text-muted-foreground"> → {m.to}: </span>
                {m.text}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
