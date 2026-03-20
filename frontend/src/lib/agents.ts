export type AgentRole = "pm" | "researcher" | "developer" | "writer" | "qa";

export type AgentStatus = "idle" | "thinking" | "working";

export type AgentDefinition = {
  id: AgentRole;
  name: string;
  title: string;
};

export const AGENTS: AgentDefinition[] = [
  { id: "pm", name: "Alex", title: "Product Manager" },
  { id: "researcher", name: "Riley", title: "Researcher" },
  { id: "developer", name: "Casey", title: "Developer" },
  { id: "writer", name: "Jordan", title: "Writer" },
  { id: "qa", name: "Sam", title: "QA" },
];

export function isAgentRole(value: string): value is AgentRole {
  return ["pm", "researcher", "developer", "writer", "qa"].includes(value);
}
