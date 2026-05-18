const BASE = import.meta.env.VITE_API_URL || "";

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
  return r.json();
}

export const api = {
  // Bot
  botStatus: () => apiFetch<any>("/api/bot/status"),
  botStart: () => apiFetch<any>("/api/bot/start", { method: "POST" }),
  botStop: () => apiFetch<any>("/api/bot/stop", { method: "POST" }),
  botUpdateConfig: (cfg: any) =>
    apiFetch<any>("/api/bot/config", { method: "PUT", body: JSON.stringify(cfg) }),
  botSignals: () => apiFetch<any>("/api/bot/signals"),

  // Trades
  listTrades: (status?: string) =>
    apiFetch<any[]>(`/api/trades${status ? `?status=${status}` : ""}`),
  manualTrade: (body: any) =>
    apiFetch<any>("/api/trades/manual", { method: "POST", body: JSON.stringify(body) }),
  closeTrade: (id: string) =>
    apiFetch<any>(`/api/trades/${id}/close`, { method: "POST" }),

  // Analysis
  analyze: (symbol: string, tf = "H1") =>
    apiFetch<any>(`/api/analysis/${symbol}?timeframe=${tf}`),
  multiScan: (symbols: string, tf = "H1") =>
    apiFetch<any[]>(`/api/analysis/multi/scan?symbols=${symbols}&timeframe=${tf}`),
  growthForecast: (days = 30) =>
    apiFetch<any>(`/api/analysis/forecast/growth?days=${days}`),

  // Stats
  walletStats: () => apiFetch<any>("/api/stats/wallet"),
  equityCurve: (limit = 60) => apiFetch<any[]>(`/api/stats/equity-curve?limit=${limit}`),
  recentPerf: (days = 7) => apiFetch<any[]>(`/api/stats/recent-performance?days=${days}`),

  // Setups / Market Analytics
  listSetups: (params?: { status?: string; symbol?: string; direction?: string; min_confidence?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.symbol) q.set("symbol", params.symbol);
    if (params?.direction) q.set("direction", params.direction);
    if (params?.min_confidence) q.set("min_confidence", String(params.min_confidence));
    return apiFetch<any[]>(`/api/setups?${q}`);
  },
  scanSetups: (force = false) =>
    apiFetch<any>(`/api/setups/scan${force ? "?force=true" : ""}`),
  getAlerts: () => apiFetch<any[]>("/api/setups/alerts"),
  dismissSetup: (id: string) =>
    apiFetch<any>(`/api/setups/${id}/dismiss`, { method: "POST" }),
};

export function createWs(onMessage: (data: any) => void): WebSocket {
  const wsBase = (import.meta.env.VITE_API_URL || window.location.origin).replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/ws/live`);
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch {} };
  return ws;
}

export function createAlertsWs(onAlert: (setup: any) => void): WebSocket {
  const wsBase = (import.meta.env.VITE_API_URL || window.location.origin).replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/ws/alerts`);
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "setup_alert") onAlert(msg.setup);
    } catch {}
  };
  // Keepalive ping every 25 s
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
  }, 25000);
  ws.onclose = () => clearInterval(ping);
  return ws;
}
