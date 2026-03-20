"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";

import type { AgentDefinition, AgentStatus } from "@/lib/agents";
import type { ThoughtEvent } from "@/lib/agent-log-types";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { mockInterAgentChatForAgent } from "@/lib/mock-inter-agent-chat";

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

type Props = {
  agent: AgentDefinition | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  status: AgentStatus;
  thoughts: ThoughtEvent[];
};

export function AgentDeepDiveSheet({
  agent,
  open,
  onOpenChange,
  status,
  thoughts,
}: Props) {
  if (!agent) return null;

  const monologue = thoughts.filter(
    (t) => t.agent.toLowerCase() === agent.id
  );
  const chatForAgent = mockInterAgentChatForAgent(agent.id);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-lg">
        <SheetHeader className="space-y-1 pr-8 text-left">
          <SheetTitle className="flex items-center gap-2">
            {agent.name}
            <Badge variant={statusVariant(status)}>{statusLabel[status]}</Badge>
          </SheetTitle>
          <SheetDescription>{agent.title}</SheetDescription>
        </SheetHeader>
        <div className="flex flex-1 flex-col gap-4 overflow-hidden px-4 pb-6 pt-2">
          <Link
            href={`/agents/${agent.id}`}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "inline-flex w-fit gap-2"
            )}
          >
            Open full deep dive
            <ExternalLink className="size-3.5" />
          </Link>
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Internal monologue
            </h3>
            <ScrollArea className="h-40 rounded-md border bg-muted/30 p-3">
              {monologue.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No streamed thoughts yet. Run the workflow or wait for agent
                  activity.
                </p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {monologue.map((t, i) => (
                    <li key={`${t.ts}-${i}`} className="leading-snug">
                      <span className="text-muted-foreground">
                        {new Date(t.ts * 1000).toLocaleTimeString()}
                      </span>{" "}
                      {t.thought}
                    </li>
                  ))}
                </ul>
              )}
            </ScrollArea>
          </div>
          <Separator />
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Chat with other agents
            </h3>
            <ScrollArea className="h-36 rounded-md border p-3">
              <ul className="space-y-2 text-sm">
                {chatForAgent.map((m, i) => (
                  <li key={i} className="leading-snug">
                    <span className="font-medium">{m.from}</span>
                    <span className="text-muted-foreground"> → {m.to}: </span>
                    {m.text}
                  </li>
                ))}
              </ul>
            </ScrollArea>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
