import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AGENTS, isAgentRole } from "@/lib/agents";
import { AgentDeepDivePage } from "@/components/agent-deep-dive-page";
import { buttonVariants } from "@/components/ui/button-variants";
import { cn } from "@/lib/utils";

type Props = { params: Promise<{ role: string }> };

export default async function AgentPage({ params }: Props) {
  const { role } = await params;
  if (!isAgentRole(role)) notFound();

  const agent = AGENTS.find((a) => a.id === role);
  if (!agent) notFound();

  return (
    <div className="flex flex-1 flex-col gap-6 py-4 md:py-6">
      <div className="flex items-center gap-3">
        <Link
          href="/"
          aria-label="Back to dashboard"
          className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {agent.name} · {agent.title}
          </h1>
          <p className="text-sm text-muted-foreground">
            Deep dive: internal monologue and inter-agent chat.
          </p>
        </div>
      </div>
      <AgentDeepDivePage agent={agent} />
    </div>
  );
}
