"use client";

import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import GridLayout, { type Layout, verticalCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import Link from "next/link";
import { GripVertical, Loader2, Play } from "lucide-react";

import { AGENTS, type AgentRole, type AgentStatus } from "@/lib/agents";
import { getApiBaseUrl } from "@/lib/env";
import { useAgentThoughts } from "@/context/agent-thoughts-context";
import { AgentDeepDiveSheet } from "@/components/agent-deep-dive-sheet";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

const defaultLayout: Layout = [
  { i: "pm", x: 0, y: 0, w: 3, h: 9, minW: 2, minH: 4 },
  { i: "researcher", x: 3, y: 0, w: 3, h: 9, minW: 2, minH: 4 },
  { i: "dev", x: 6, y: 0, w: 3, h: 9, minW: 2, minH: 4 },
  { i: "qa", x: 9, y: 0, w: 3, h: 9, minW: 2, minH: 4 },
  { i: "thoughts", x: 0, y: 9, w: 12, h: 7, minW: 4, minH: 4 },
];

const statusLabel: Record<AgentStatus, string> = {
  idle: "Idle",
  thinking: "Thinking",
  working: "Working",
};

function statusVariant(
  s: AgentStatus
): "secondary" | "default" | "outline" {
  if (s === "working") return "default";
  if (s === "thinking") return "secondary";
  return "outline";
}

function deriveStatuses(
  thoughts: { agent: string; ts: number }[]
): Record<AgentRole, AgentStatus> {
  const base: Record<AgentRole, AgentStatus> = {
    pm: "idle",
    researcher: "idle",
    dev: "idle",
    qa: "idle",
  };
  const now = Date.now() / 1000;
  const recent = 2.5;
  for (const t of thoughts) {
    const role = t.agent.toLowerCase() as AgentRole;
    if (role in base && now - t.ts < recent) {
      base[role] = "working";
    }
  }
  return base;
}

export function DashboardView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);
  const [layout, setLayout] = useState<Layout>(defaultLayout);
  const [sheetAgentId, setSheetAgentId] = useState<AgentRole | null>(null);
  const [graphRunning, setGraphRunning] = useState(false);
  const { thoughts, connected, thoughtsForAgent } = useAgentThoughts();

  const statuses = useMemo(() => deriveStatuses(thoughts), [thoughts]);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(Math.floor(w));
    });
    ro.observe(el);
    setWidth(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);

  const onLayoutChange = useCallback((next: Layout) => {
    setLayout(next);
  }, []);

  const runWorkflow = async () => {
    setGraphRunning(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/graph/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: "Research & develop cycle" }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e) {
      console.error(e);
    } finally {
      setGraphRunning(false);
    }
  };

  const sheetAgent = useMemo(
    () => AGENTS.find((a) => a.id === sheetAgentId) ?? null,
    [sheetAgentId]
  );

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-auto p-4 md:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Drag tiles to rearrange. Click an agent for a deep dive.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={connected ? "default" : "secondary"}>
            {connected ? "Live thoughts" : "WS disconnected"}
          </Badge>
          <Button
            size="sm"
            onClick={runWorkflow}
            disabled={graphRunning}
            className="gap-2"
          >
            {graphRunning ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
            Run research & develop
          </Button>
        </div>
      </div>

      <div ref={containerRef} className="min-h-[520px] w-full max-w-full">
        {width > 0 && (
          <GridLayout
            className="layout"
            layout={layout}
            width={width}
            gridConfig={{
              cols: 12,
              rowHeight: 28,
              margin: [12, 12],
              containerPadding: [0, 0],
            }}
            dragConfig={{ enabled: true, handle: ".drag-handle" }}
            compactor={verticalCompactor}
            onLayoutChange={onLayoutChange}
          >
            {AGENTS.map((agent) => (
              <div key={agent.id} className="rounded-xl">
                <Card className="h-full border shadow-sm">
                  <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
                    <div className="min-w-0">
                      <button
                        type="button"
                        className="drag-handle cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing"
                        aria-label="Drag to move tile"
                      >
                        <GripVertical className="size-5" />
                      </button>
                      <CardTitle className="truncate text-base">
                        {agent.name}
                      </CardTitle>
                      <CardDescription className="truncate">
                        {agent.title}
                      </CardDescription>
                    </div>
                    <Badge variant={statusVariant(statuses[agent.id])}>
                      {statusLabel[statuses[agent.id]]}
                    </Badge>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="w-full"
                      onClick={() => setSheetAgentId(agent.id)}
                    >
                      Deep dive
                    </Button>
                    <Link
                      href={`/agents/${agent.id}`}
                      className={cn(
                        buttonVariants({ variant: "ghost", size: "sm" }),
                        "w-full justify-center"
                      )}
                    >
                      Full page
                    </Link>
                  </CardContent>
                </Card>
              </div>
            ))}
            <div key="thoughts" className="rounded-xl">
              <Card className="h-full border shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Agent thought stream</CardTitle>
                  <CardDescription>
                    WebSocket feed from <code className="text-xs">/ws/agent-thoughts</code>
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 pb-2">
                    <button
                      type="button"
                      className="drag-handle cursor-grab text-muted-foreground hover:text-foreground"
                      aria-label="Drag to move panel"
                    >
                      <GripVertical className="size-5" />
                    </button>
                  </div>
                  <ScrollArea className="h-[180px] rounded-md border bg-muted/20 p-3">
                    {thoughts.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Connect the backend and run the workflow to see thoughts.
                      </p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {thoughts.slice(-40).map((t, i) => (
                          <li key={`${t.ts}-${i}`} className="leading-snug">
                            <span className="font-medium text-primary">
                              {t.agent}
                            </span>
                            <span className="text-muted-foreground"> · </span>
                            {t.thought}
                          </li>
                        ))}
                      </ul>
                    )}
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </GridLayout>
        )}
      </div>

      <AgentDeepDiveSheet
        agent={sheetAgent}
        open={sheetAgentId !== null}
        onOpenChange={(o) => !o && setSheetAgentId(null)}
        status={sheetAgent ? statuses[sheetAgent.id] : "idle"}
        thoughts={sheetAgent ? thoughtsForAgent(sheetAgent.id) : []}
      />
    </div>
  );
}
