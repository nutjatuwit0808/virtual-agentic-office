"use client";

import Link from "next/link";
import { LayoutDashboard, Settings } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Sidebar collapsible="icon">
        <SidebarHeader className="border-b border-sidebar-border px-2 py-3">
          <div className="flex flex-col gap-0.5 group-data-[collapsible=icon]:items-center">
            <span className="truncate text-sm font-semibold tracking-tight">
              Agentic Office
            </span>
            <span className="truncate text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              Multi-agent workspace
            </span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Navigate</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    tooltip="Dashboard"
                    render={
                      <Link href="/" className="flex items-center gap-2">
                        <LayoutDashboard />
                        <span>Dashboard</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    tooltip="Settings"
                    render={
                      <Link href="/settings" className="flex items-center gap-2">
                        <Settings />
                        <span>Settings</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarSeparator />
        </SidebarContent>
        <SidebarRail />
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <div className="text-sm font-medium text-muted-foreground">
            Virtual office
          </div>
        </header>
        <div className="flex flex-1 flex-col overflow-hidden">{children}</div>
      </SidebarInset>
    </>
  );
}
