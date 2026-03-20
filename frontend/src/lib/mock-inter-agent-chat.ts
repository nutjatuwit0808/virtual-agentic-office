import type { AgentRole } from "@/lib/agents";

export type MockInterAgentMessage = {
  from: AgentRole;
  to: AgentRole;
  text: string;
};

export const MOCK_INTER_AGENT_CHAT: MockInterAgentMessage[] = [
  {
    from: "pm",
    to: "researcher",
    text: "Can you summarize competitor positioning?",
  },
  {
    from: "researcher",
    to: "pm",
    text: "Draft summary is in shared artifacts.",
  },
  {
    from: "writer",
    to: "qa",
    text: "Pushing draft for review and smoke tests.",
  },
];

export function mockInterAgentChatForAgent(
  agentId: AgentRole
): MockInterAgentMessage[] {
  return MOCK_INTER_AGENT_CHAT.filter(
    (m) => m.from === agentId || m.to === agentId
  );
}
