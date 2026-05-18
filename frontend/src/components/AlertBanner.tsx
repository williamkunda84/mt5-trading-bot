/**
 * AlertBanner
 * Horizontal scrolling strip that shows high-priority setup alerts.
 * Requests browser notification permission on first alert.
 */
import { useEffect, useRef, useState } from "react";
import { Bell, BellOff, X, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import { createAlertsWs } from "../lib/api";

export interface SetupAlert {
  id: string;
  symbol: string;
  timeframe: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  confidence: number;
  eta_minutes: number | null;
  strategies_confirmed: string[];
  status: string;
  detected_at: string;
}

interface Props {
  onAlertClick?: (alert: SetupAlert) => void;
}

function useNotificationPermission() {
  const [perm, setPerm] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "denied"
  );
  const request = async () => {
    if (typeof Notification === "undefined") return;
    const result = await Notification.requestPermission();
    setPerm(result);
  };
  return { perm, request };
}

function sendBrowserNotification(alert: SetupAlert) {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  const dir = alert.direction === "buy" ? "📈 BUY" : "📉 SELL";
  const eta = alert.eta_minutes === 0 ? "NOW" : `in ${alert.eta_minutes}min`;
  new Notification(`${dir} Setup — ${alert.symbol} ${alert.timeframe}`, {
    body: `${alert.strategies_confirmed.length} strategies • ${alert.confidence.toFixed(0)}% confidence • Entry ${alert.entry_price} • ${eta}`,
    icon: "/favicon.ico",
    tag: alert.id,
  });
}

export default function AlertBanner({ onAlertClick }: Props) {
  const [alerts, setAlerts] = useState<SetupAlert[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const { perm, request } = useNotificationPermission();

  // Connect to /ws/alerts
  useEffect(() => {
    let retryDelay = 3000;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    function connect() {
      if (stopped) return;
      try {
        const ws = createAlertsWs((setup: SetupAlert) => {
          retryDelay = 3000;
          setAlerts((prev) => {
            if (prev.find((a) => a.id === setup.id)) return prev;
            const next = [setup, ...prev].slice(0, 10);
            sendBrowserNotification(setup);
            return next;
          });
        });
        ws.onclose = () => {
          if (!stopped) { timer = setTimeout(connect, retryDelay); retryDelay = Math.min(retryDelay * 2, 30000); }
        };
        ws.onerror = () => ws.close();
        wsRef.current = ws;
      } catch {
        timer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      }
    }
    connect();
    return () => { stopped = true; clearTimeout(timer); wsRef.current?.close(); };
  }, []);

  const visible = alerts.filter((a) => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  return (
    <div className="bg-[#0d1117] border-b border-yellow-500/30 px-4 py-2">
      <div className="flex items-center gap-3">
        {/* Bell icon + label */}
        <div className="flex items-center gap-1.5 shrink-0">
          <AlertTriangle size={13} className="text-yellow-400 animate-pulse" />
          <span className="text-[10px] font-bold uppercase text-yellow-400 tracking-wider">
            Alerts
          </span>
          <span className="text-[10px] bg-yellow-400/20 text-yellow-400 rounded-full px-1.5 py-0.5 font-bold">
            {visible.length}
          </span>
        </div>

        {/* Scrollable pills */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar flex-1">
          {visible.map((alert) => {
            const isBuy = alert.direction === "buy";
            const eta = alert.eta_minutes;
            return (
              <button
                key={alert.id}
                onClick={() => onAlertClick?.(alert)}
                className={`flex items-center gap-2 shrink-0 px-3 py-1 rounded-full border text-[11px] font-semibold transition-all hover:brightness-125 ${
                  isBuy
                    ? "border-bull/50 bg-bull/10 text-bull"
                    : "border-bear/50 bg-bear/10 text-bear"
                }`}
              >
                {isBuy ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                <span className="text-white">{alert.symbol}</span>
                <span className="opacity-70">{alert.timeframe}</span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isBuy ? "bg-bull/20" : "bg-bear/20"}`}>
                  {isBuy ? "BUY" : "SELL"}
                </span>
                <span className="text-white/70">{alert.confidence.toFixed(0)}%</span>
                {eta !== null && eta !== undefined && (
                  <span className={`text-[10px] px-1 rounded ${eta === 0 ? "text-yellow-400 bg-yellow-400/20" : "text-white/50"}`}>
                    {eta === 0 ? "NOW" : `${eta}m`}
                  </span>
                )}
                <span
                  onClick={(e) => { e.stopPropagation(); setDismissed((d) => new Set([...d, alert.id])); }}
                  className="ml-1 text-white/30 hover:text-white/80 cursor-pointer"
                >
                  <X size={10} />
                </span>
              </button>
            );
          })}
        </div>

        {/* Notification permission toggle */}
        <button
          onClick={request}
          title={perm === "granted" ? "Browser notifications ON" : "Enable browser notifications"}
          className="shrink-0 ml-1"
        >
          {perm === "granted"
            ? <Bell size={13} className="text-yellow-400" />
            : <BellOff size={13} className="text-muted hover:text-white" />
          }
        </button>
      </div>
    </div>
  );
}
