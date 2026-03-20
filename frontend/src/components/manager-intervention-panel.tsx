"use client";

import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export type ManagerEscalationOption = {
  id: string;
  label: string;
  description: string;
};

export type ManagerInterventionPanelProps = {
  summary: string;
  options: ManagerEscalationOption[];
  threadId: string;
  disabled?: boolean;
  onResume: (
    choice: "force_approve" | "change_instructions" | "terminate",
    newInstructions?: string
  ) => void | Promise<void>;
};

export function ManagerInterventionPanel({
  summary,
  options,
  threadId,
  disabled = false,
  onResume,
}: ManagerInterventionPanelProps) {
  const [directOrder, setDirectOrder] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (
    choice: "force_approve" | "change_instructions" | "terminate"
  ) => {
    setBusy(true);
    try {
      const extra =
        choice === "change_instructions"
          ? directOrder.trim() || undefined
          : undefined;
      await onResume(choice, extra);
      setDirectOrder("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      className={cn(
        "border-2 border-amber-500/60 bg-gradient-to-b from-amber-500/10 to-background shadow-md",
        "ring-2 ring-amber-500/20"
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start gap-2">
          <div className="mt-0.5 rounded-md bg-amber-500/20 p-1.5">
            <AlertTriangle className="size-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-lg">Manager intervention</CardTitle>
            <CardDescription>
              The office is paused for escalation. Review the summary and issue a
              direct order to break the loop. Thread{" "}
              <code className="rounded bg-muted px-1 text-xs">{threadId.slice(0, 12)}…</code>
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Summary
          </p>
          <ScrollArea className="max-h-[160px] rounded-md border border-amber-500/25 bg-background/80 p-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {summary || "No summary provided."}
            </p>
          </ScrollArea>
        </div>

        {options.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Choose an action
            </p>
            <ul className="space-y-2">
              {options.map((opt) => (
                <li
                  key={opt.id}
                  className="rounded-lg border border-border/80 bg-muted/20 px-3 py-2 text-sm"
                >
                  <span className="font-medium">{opt.label}</span>
                  {opt.description ? (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {opt.description}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="space-y-1.5">
          <label
            htmlFor="manager-direct-order"
            className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Direct order (optional — used with &quot;Change instructions&quot;)
          </label>
          <textarea
            id="manager-direct-order"
            rows={3}
            value={directOrder}
            onChange={(e) => setDirectOrder(e.target.value)}
            disabled={disabled || busy}
            placeholder="e.g. Accept the draft as-is for tone; only fix heading levels H2–H3."
            className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {busy ? (
            <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
          ) : null}
          <Button
            size="sm"
            className="bg-amber-600 text-white hover:bg-amber-700 dark:bg-amber-600 dark:hover:bg-amber-700"
            disabled={disabled || busy}
            onClick={() => void run("force_approve")}
          >
            Force approve
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={disabled || busy}
            onClick={() => void run("change_instructions")}
          >
            Change instructions
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || busy}
            onClick={() => void run("terminate")}
          >
            Terminate task
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
