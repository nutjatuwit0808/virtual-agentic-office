"use client";

import type { ButtonHTMLAttributes } from "react";
import Link from "next/link";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";

import type { AgentDefinition, AgentStatus } from "@/lib/agents";
import type { LlmTokenUsage } from "@/hooks/useAgentLog";
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

export type AgentCardProps = {
  agent: AgentDefinition;
  status: AgentStatus;
  onDeepDive: () => void;
  /** Recent lines for this agent from the WebSocket log (thoughts, nodes, stream chunks, …). */
  logLines?: string[];
  /** Cumulative LLM API token usage for this agent in the current session / run. */
  llmUsage?: LlmTokenUsage;
  /** When true, card is visually de-emphasized (e.g. escalation mode). */
  dimmed?: boolean;
  /** Show when graph loop_counter is high (approaching escalation). */
  showLoopWarning?: boolean;
};

function formatApiTokenLine(u: LlmTokenUsage): string {
  if (u.total === 0 && u.input === 0 && u.output === 0) return "—";
  return `in ${u.input.toLocaleString()} · out ${u.output.toLocaleString()} · Σ ${u.total.toLocaleString()}`;
}

export function AgentCard({
  agent,
  status,
  onDeepDive,
  logLines = [],
  llmUsage,
  dimmed = false,
  showLoopWarning = false,
  dragHandleListeners,
}: AgentCardProps & {
  dragHandleListeners?: ButtonHTMLAttributes<HTMLButtonElement>;
}) {
  const tail = logLines.slice(-12);
  const showTerminal =
    agent.id === "developer" || tail.length > 0;
  const usage = llmUsage ?? { input: 0, output: 0, total: 0 };

  return (
    <Card
      className={cn(
        "h-full border shadow-sm transition-opacity duration-200",
        dimmed && "pointer-events-none opacity-[0.38] saturate-50"
      )}
    >
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div className="min-w-0">
          <button
            type="button"
            className="cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing"
            aria-label="Drag to reorder"
            {...dragHandleListeners}
          >
            <GripVertical className="size-5" />
          </button>
          <CardTitle className="truncate text-base">{agent.name}</CardTitle>
          <CardDescription className="truncate">{agent.title}</CardDescription>
          <p className="text-[10px] tabular-nums text-muted-foreground">
            API tokens: {formatApiTokenLine(usage)}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {showLoopWarning ? (
            <Badge
              variant="outline"
              className="border-amber-600/70 text-[10px] text-amber-800 dark:text-amber-300"
            >
              Loop warning
            </Badge>
          ) : null}
          <Badge variant={statusVariant(status)}>{statusLabel[status]}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {showTerminal ? (
          <div className="space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Terminal
            </p>
            <ScrollArea className="h-[88px] rounded-md border border-border/80 bg-muted/30 px-2 py-1.5">
              <ul className="space-y-0.5 font-mono text-[10px] leading-tight text-muted-foreground">
                {tail.length > 0 ? (
                  tail.map((line, i) => (
                    <li key={i} className="break-words">
                      {line}
                    </li>
                  ))
                ) : (
                  <li className="break-words text-muted-foreground/90">
                    Sandbox idle — run the workflow to stream E2B output.
                  </li>
                )}
              </ul>
            </ScrollArea>
          </div>
        ) : null}
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          onClick={onDeepDive}
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
  );
}

export function SortableAgentCard(props: AgentCardProps) {
  const { agent } = props;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: agent.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.85 : 1,
    zIndex: isDragging ? 1 : 0,
  };

  return (
    <div ref={setNodeRef} style={style} className="rounded-xl" {...attributes}>
      <AgentCard {...props} dragHandleListeners={listeners} />
    </div>
  );
}
