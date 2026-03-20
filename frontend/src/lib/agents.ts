export type AgentRole = "pm" | "researcher" | "dev" | "qa";

export type AgentStatus = "idle" | "thinking" | "working";

export type AgentDefinition = {
  id: AgentRole;
  name: string;
  title: string;
};

export const AGENTS: AgentDefinition[] = [
  { id: "pm", name: "Alex", title: "Product Manager" },
  { id: "researcher", name: "Riley", title: "Researcher" },
  { id: "dev", name: "Jordan", title: "Developer" },
  { id: "qa", name: "Sam", title: "QA" },
];

export function isAgentRole(value: string): value is AgentRole {
  return ["pm", "researcher", "dev", "qa"].includes(value);
}
