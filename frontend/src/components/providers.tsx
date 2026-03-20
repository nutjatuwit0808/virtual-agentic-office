"use client";

import type { ReactNode } from "react";

import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AgentThoughtsProvider } from "@/context/agent-thoughts-context";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <AgentThoughtsProvider>
        <SidebarProvider>{children}</SidebarProvider>
      </AgentThoughtsProvider>
    </TooltipProvider>
  );
}
