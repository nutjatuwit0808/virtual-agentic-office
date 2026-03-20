export type LlmTokenUsage = {
  input: number;
  output: number;
  total: number;
};

export type ThoughtEvent = {
  agent: string;
  thought: string;
  ts: number;
};

export type EscalationState = {
  threadId: string;
  summary: string;
  options: Array<{ id: string; label: string; description: string }>;
};
