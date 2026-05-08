import { useEffect, useRef, useState } from "react";
import { createWs } from "../lib/api";

export interface LiveTick {
  prices: Record<string, { bid: number; ask: number; spread: number }>;
  account: { balance: number; equity: number; free_margin: number };
  bot_running: boolean;
  signals: Record<string, any>;
  tick: number;
}

export function useLive() {
  const [tick, setTick] = useState<LiveTick | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let retryDelay = 2000;
    let timeoutId: ReturnType<typeof setTimeout>;
    let stopped = false;

    function connect() {
      if (stopped) return;
      try {
        const ws = createWs((data) => {
          setTick(data);
          setConnected(true);
          retryDelay = 2000; // reset on success
        });
        ws.onopen = () => { setConnected(true); retryDelay = 2000; };
        ws.onclose = () => {
          if (stopped) return;
          setConnected(false);
          timeoutId = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30000); // exponential backoff, max 30s
        };
        ws.onerror = () => ws.close();
        wsRef.current = ws;
      } catch {
        timeoutId = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      }
    }
    connect();
    return () => { stopped = true; clearTimeout(timeoutId); wsRef.current?.close(); };
  }, []);

  return { tick, connected };
}
