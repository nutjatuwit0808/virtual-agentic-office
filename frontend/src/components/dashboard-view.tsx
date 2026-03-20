"use client";

import { useCallback, useMemo, useState } from "react";
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { Loader2, Play } from "lucide-react";

import { SortableAgentCard } from "@/components/agent-card";
import { ManagerInterventionPanel } from "@/components/manager-intervention-panel";
import { AGENTS, type AgentRole } from "@/lib/agents";
import { getApiBaseUrl } from "@/lib/env";
import { useAgentLog } from "@/context/agent-thoughts-context";
import { LOOP_WARNING_THRESHOLD } from "@/lib/office-ui";
import type { EscalationState } from "@/hooks/useAgentLog";
import { AgentDeepDiveSheet } from "@/components/agent-deep-dive-sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { OutputGallery } from "@/components/output-gallery";
import { cn } from "@/lib/utils";

function agentById(id: AgentRole) {
  return AGENTS.find((a) => a.id === id)!;
}

export function DashboardView() {
  const [order, setOrder] = useState<AgentRole[]>(() =>
    AGENTS.map((a) => a.id)
  );
  const [sheetAgentId, setSheetAgentId] = useState<AgentRole | null>(null);
  const [graphRunning, setGraphRunning] = useState(false);
  const [galleryRefresh, setGalleryRefresh] = useState(0);
  const [workflowTopic, setWorkflowTopic] = useState("Research → write cycle");
  const [humanFeedback, setHumanFeedback] = useState("");
  const {
    connected,
    thoughtsForAgent,
    statusByAgent,
    logForAgent,
    globalLog,
    loopCounter,
    escalation,
    applyEscalationFromApi,
    beginGraphRun,
    usageByAgent,
    usageTotals,
  } = useAgentLog();

  const escalationMode = escalation !== null;

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  );

  const onDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setOrder((items) => {
      const oldIndex = items.indexOf(active.id as AgentRole);
      const newIndex = items.indexOf(over.id as AgentRole);
      if (oldIndex < 0 || newIndex < 0) return items;
      return arrayMove(items, oldIndex, newIndex);
    });
  }, []);

  const parseEscalationFromState = (
    threadId: string,
    artifacts: Record<string, unknown> | undefined
  ): EscalationState => {
    const summary = String(artifacts?.escalation_summary ?? "");
    const rawOpts = artifacts?.escalation_options;
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
    return { threadId, summary, options };
  };

  const runWorkflow = async () => {
    const topic = workflowTopic.trim();
    if (!topic) return;
    setGraphRunning(true);
    beginGraphRun();
    try {
      const body: { topic: string; human_feedback?: string } = { topic };
      const fb = humanFeedback.trim();
      if (fb) body.human_feedback = fb;
      const res = await fetch(`${getApiBaseUrl()}/api/graph/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as {
        interrupted?: boolean;
        thread_id?: string;
        state?: { artifacts?: Record<string, unknown> };
      };
      if (data.interrupted && data.thread_id) {
        applyEscalationFromApi(
          parseEscalationFromState(
            data.thread_id,
            data.state?.artifacts
          )
        );
      }
      setGalleryRefresh((n) => n + 1);
    } catch (e) {
      console.error(e);
    } finally {
      setGraphRunning(false);
    }
  };

  const resumeEscalation = async (
    choice: "force_approve" | "change_instructions" | "terminate",
    newInstructions?: string
  ) => {
    const tid = escalation?.threadId;
    if (!tid) return;
    setGraphRunning(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/graph/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: tid,
          choice,
          new_instructions: newInstructions,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      applyEscalationFromApi(null);
      setGalleryRefresh((n) => n + 1);
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
    <div className="flex flex-1 flex-col gap-4 overflow-auto py-4 md:py-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Drag agent cards to reorder. Click an agent for a deep dive.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge variant={connected ? "default" : "secondary"}>
              {connected ? "Live thoughts" : "WS disconnected"}
            </Badge>
            <Button
              size="sm"
              onClick={runWorkflow}
              disabled={graphRunning || !workflowTopic.trim()}
              className="gap-2"
            >
              {graphRunning ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              Run research → develop → write
            </Button>
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">
            API tokens (session): Σ{" "}
            {usageTotals.total.toLocaleString()} · in{" "}
            {usageTotals.input.toLocaleString()} · out{" "}
            {usageTotals.output.toLocaleString()}
          </p>
        </div>
      </div>

      <Card className="border shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Workflow input</CardTitle>
          <CardDescription>
            Topic is sent to <code className="text-xs">POST /api/graph/run</code>.
            Optional note is stored as long-term memory context for this run.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label
              htmlFor="workflow-topic"
              className="text-sm font-medium leading-none"
            >
              Topic
            </label>
            <Input
              id="workflow-topic"
              value={workflowTopic}
              onChange={(e) => setWorkflowTopic(e.target.value)}
              maxLength={500}
              placeholder="What should the office work on?"
              disabled={graphRunning}
              aria-invalid={!workflowTopic.trim()}
            />
            <p className="text-xs text-muted-foreground">
              {workflowTopic.length}/500 · required
            </p>
          </div>
          <div className="space-y-2">
            <label
              htmlFor="workflow-feedback"
              className="text-sm font-medium leading-none"
            >
              Memory note <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="workflow-feedback"
              value={humanFeedback}
              onChange={(e) => setHumanFeedback(e.target.value)}
              maxLength={8000}
              placeholder="Constraints, audience, tone, or links the agents should respect…"
              disabled={graphRunning}
              rows={3}
              className={cn(
                "min-h-[72px] w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30"
              )}
            />
            <p className="text-xs text-muted-foreground">
              {humanFeedback.length}/8000
            </p>
          </div>
        </CardContent>
      </Card>

      {escalationMode && escalation ? (
        <ManagerInterventionPanel
          threadId={escalation.threadId}
          summary={escalation.summary}
          options={escalation.options}
          disabled={graphRunning}
          onResume={(choice, newInstructions) =>
            resumeEscalation(choice, newInstructions)
          }
        />
      ) : null}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
      >
        <SortableContext items={order} strategy={rectSortingStrategy}>
          <div
            className={
              escalationMode
                ? "pointer-events-none"
                : undefined
            }
          >
            <div className="grid w-full max-w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
              {order.map((id) => (
                <SortableAgentCard
                  key={id}
                  agent={agentById(id)}
                  status={statusByAgent[id]}
                  logLines={logForAgent(id)}
                  llmUsage={usageByAgent[id]}
                  onDeepDive={() => setSheetAgentId(id)}
                  dimmed={escalationMode}
                  showLoopWarning={loopCounter >= LOOP_WARNING_THRESHOLD}
                />
              ))}
            </div>
          </div>
        </SortableContext>
      </DndContext>

      <Card className="border shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Agent activity stream</CardTitle>
          <CardDescription>
            Live log from <code className="text-xs">/ws/agent-thoughts</code>{" "}
            (thoughts, nodes, tools, stream chunks, API token events)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[180px] rounded-md border bg-muted/20 p-3">
            {globalLog.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Connect the backend and run the workflow to see the stream.
              </p>
            ) : (
              <ul className="space-y-1.5 font-mono text-xs leading-snug">
                {globalLog.slice(-40).map((line, i) => (
                  <li key={i} className="break-words">
                    {line}
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      <OutputGallery refreshKey={galleryRefresh} />

      <AgentDeepDiveSheet
        agent={sheetAgent}
        open={sheetAgentId !== null}
        onOpenChange={(o) => !o && setSheetAgentId(null)}
        status={sheetAgent ? statusByAgent[sheetAgent.id] : "idle"}
        thoughts={sheetAgent ? thoughtsForAgent(sheetAgent.id) : []}
      />
    </div>
  );
}
