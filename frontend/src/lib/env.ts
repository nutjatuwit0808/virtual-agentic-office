export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export function getWsBaseUrl(): string {
  return process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
}
