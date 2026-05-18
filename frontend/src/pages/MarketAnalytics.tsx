import { useCallback, useEffect, useRef, useState } from "react";
import {
  RefreshCw, Filter, SlidersHorizontal, Bell,
  TrendingUp, TrendingDown, Clock, AlertTriangle,
  ChevronDown,
} from "lucide-react";
import { api } from "../lib/api";
import SetupCard from "../components/SetupCard";

const SYMBOLS = ["All", "EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY", "AUDUSD", "EURJPY"];
const TIMEFRAMES = ["All", "M15", "H1", "H4"];
const DIRECTIONS = ["All", "buy", "sell"];
const STRATEGIES = [
  "EMA Confluence", "RSI Divergence", "MACD Crossover",
  "BB Squeeze Breakout", "S/R Bounce", "ICT Session Play",
  "Fibonacci", "Candlestick Pattern",
];

interface Setup {
  id: string;
  symbol: string;
  timeframe: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  take_profit_3: number;
  confidence: number;
  rr_ratio: number;
  strategies_confirmed: string[];
  strategy_details: any[];
  status: string;
  eta_minutes: number | null;
  detected_at: string;
  notes: string;
}

// ─── Strategy description panel ───────────────────────────────────────────────
const STRATEGY_INFO: Record<string, { desc: string; when: string; color: string }> = {
  "EMA Confluence":     { color: "text-blue-400",   desc: "Price aligns with EMA 20/50/200 stack", when: "Pullback to EMA20 in trend direction" },
  "RSI Divergence":     { color: "text-purple-400", desc: "Price and RSI move in opposite directions", when: "Price HH + RSI LH (bear) or LL + HL (bull)" },
  "MACD Crossover":     { color: "text-cyan-400",   desc: "MACD line crosses signal line", when: "Histogram flips positive/negative" },
  "BB Squeeze Breakout":{ color: "text-orange-400", desc: "Volatility compression followed by expansion", when: "BB width at N-bar low then price breaks band" },
  "S/R Bounce":         { color: "text-pink-400",   desc: "Price reacts at key support or resistance", when: "Price within 0.15% of S/R level" },
  "ICT Session Play":   { color: "text-yellow-400", desc: "Momentum at major session opens (London/NY/Tokyo)", when: "Within 60 min of session open + trend alignment" },
  "Fibonacci":          { color: "text-emerald-400",desc: "Price at 38.2%, 50%, or 61.8% retracement", when: "Fib level + RSI + EMA confirmation" },
  "Candlestick Pattern":{ color: "text-rose-400",   desc: "Engulfing, pin bar, hammer, shooting star", when: "Pattern forms at key structural level" },
};

function StrategyLegend() {
  const [open, setOpen] = useState(false);
  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-white hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-brand" />
          Strategy Reference Guide
        </div>
        <ChevronDown size={14} className={`text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-0 border-t border-bg-border divide-x divide-y divide-bg-border">
          {Object.entries(STRATEGY_INFO).map(([name, info]) => (
            <div key={name} className="px-4 py-3 space-y-1">
              <div className={`text-[11px] font-bold ${info.color}`}>{name}</div>
              <div className="text-[10px] text-white/70">{info.desc}</div>
              <div className="text-[9px] text-muted">↳ {info.when}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatPill({ label, value, color = "text-white" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="card px-4 py-3 flex flex-col gap-0.5">
      <div className="text-[10px] text-muted uppercase tracking-wider">{label}</div>
      <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}

export default function MarketAnalytics() {
  const [setups, setSetups] = useState<Setup[]>([]);
  const [alerts, setAlerts] = useState<Setup[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [scanning, setScanning] = useState(false);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  // Filters
  const [filterSym, setFilterSym] = useState("All");
  const [filterTf, setFilterTf] = useState("All");
  const [filterDir, setFilterDir] = useState("All");
  const [filterStrat, setFilterStrat] = useState("All");
  const [minConf, setMinConf] = useState(55);
  const [showFilters, setShowFilters] = useState(false);

  // Trade modal state
  const [tradeSetup, setTradeSetup] = useState<Setup | null>(null);
  const [tradePlaced, setTradePlaced] = useState(false);

  const load = useCallback(async (force = false) => {
    setScanning(true);
    try {
      const [scanRes, alertRes] = await Promise.all([
        api.scanSetups(force).catch(() => ({ setups: [] })),
        api.getAlerts().catch(() => []),
      ]);
      setSetups(scanRes.setups ?? []);
      setAlerts(alertRes);
      setScannedAt(scanRes.scanned_at ?? new Date().toISOString());
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(() => load(false), 90_000);
    return () => clearInterval(id);
  }, [load]);

  const handleDismiss = async (id: string) => {
    setDismissed((d) => new Set([...d, id]));
    await api.dismissSetup(id).catch(() => {});
  };

  const handleAlertClick = (alert: Setup) => {
    setHighlightId(alert.id);
    setTimeout(() => setHighlightId(null), 4000);
    document.getElementById(`setup-${alert.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleTrade = async (setup: Setup) => {
    setTradeSetup(setup);
    setTradePlaced(false);
  };

  const confirmTrade = async () => {
    if (!tradeSetup) return;
    try {
      await api.manualTrade({
        symbol: tradeSetup.symbol,
        order_type: tradeSetup.direction,
        volume: 0.01,
        stop_loss: tradeSetup.stop_loss,
        take_profit: tradeSetup.take_profit_2,
      });
      setTradePlaced(true);
    } catch (e) {
      alert("Trade failed — check backend connection");
    }
  };

  // Filtered setups
  const visible = setups.filter((s) => {
    if (dismissed.has(s.id)) return false;
    if (filterSym !== "All" && s.symbol !== filterSym) return false;
    if (filterTf !== "All" && s.timeframe !== filterTf) return false;
    if (filterDir !== "All" && s.direction !== filterDir) return false;
    if (filterStrat !== "All" && !s.strategies_confirmed.includes(filterStrat)) return false;
    if (s.confidence < minConf) return false;
    return true;
  });

  const alertsVisible = alerts.filter((a) => !dismissed.has(a.id));
  const buyCount = visible.filter((s) => s.direction === "buy").length;
  const sellCount = visible.filter((s) => s.direction === "sell").length;
  const confirmed = visible.filter((s) => s.status === "confirmed").length;
  const forming = visible.filter((s) => s.status === "forming").length;
  const avgConf = visible.length ? (visible.reduce((a, s) => a + s.confidence, 0) / visible.length).toFixed(0) : "—";

  return (
    <div className="p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold text-white">Market Analytics</h1>
        <div className="flex items-center gap-1.5 text-[11px] text-muted ml-1">
          {scannedAt && <>Last scan: {new Date(scannedAt).toLocaleTimeString()}</>}
          {scanning && <span className="text-brand animate-pulse">Scanning…</span>}
        </div>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] border transition-colors ${
              showFilters ? "bg-brand/20 text-brand border-brand/40" : "text-muted border-bg-border hover:text-white"
            }`}
          >
            <Filter size={13} /> Filters
          </button>
          <button
            onClick={() => load(true)}
            disabled={scanning}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand/20 hover:bg-brand/30 text-brand border border-brand/40 rounded text-[12px] transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={scanning ? "animate-spin" : ""} />
            Scan Now
          </button>
        </div>
      </div>

      {/* Alert strip for upcoming setups */}
      {alertsVisible.length > 0 && (
        <div className="card border-yellow-500/30 bg-yellow-500/5 p-3">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={13} className="text-yellow-400 animate-pulse" />
            <span className="text-[11px] font-bold text-yellow-400 uppercase tracking-wider">
              {alertsVisible.length} Setup{alertsVisible.length > 1 ? "s" : ""} Triggering Within 1 Hour
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {alertsVisible.map((a) => (
              <button
                key={a.id}
                onClick={() => handleAlertClick(a)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-semibold transition-all hover:brightness-125 ${
                  a.direction === "buy"
                    ? "border-bull/50 bg-bull/10 text-bull"
                    : "border-bear/50 bg-bear/10 text-bear"
                }`}
              >
                {a.direction === "buy" ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                <span className="text-white">{a.symbol}</span>
                <span className="opacity-60">{a.timeframe}</span>
                <span className="font-bold">{a.direction.toUpperCase()}</span>
                <span className="text-white/60">{a.confidence.toFixed(0)}%</span>
                {a.eta_minutes !== null && a.eta_minutes !== undefined && (
                  <span className="flex items-center gap-0.5 text-[10px] bg-yellow-400/20 text-yellow-400 px-1 rounded">
                    <Clock size={8} />
                    {a.eta_minutes === 0 ? "NOW" : `${a.eta_minutes}m`}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatPill label="Total Setups" value={visible.length} />
        <StatPill label="Buy Setups" value={buyCount} color="text-bull" />
        <StatPill label="Sell Setups" value={sellCount} color="text-bear" />
        <StatPill label="Confirmed" value={confirmed} color="text-yellow-400" />
        <StatPill label="Avg Confidence" value={`${avgConf}%`} />
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="card p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
          <div>
            <label className="text-[10px] text-muted uppercase tracking-wider">Symbol</label>
            <select className="mt-1 w-full bg-bg border border-bg-border rounded px-2 py-1.5 text-[12px] text-white outline-none"
              value={filterSym} onChange={(e) => setFilterSym(e.target.value)}>
              {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted uppercase tracking-wider">Timeframe</label>
            <select className="mt-1 w-full bg-bg border border-bg-border rounded px-2 py-1.5 text-[12px] text-white outline-none"
              value={filterTf} onChange={(e) => setFilterTf(e.target.value)}>
              {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted uppercase tracking-wider">Direction</label>
            <select className="mt-1 w-full bg-bg border border-bg-border rounded px-2 py-1.5 text-[12px] text-white outline-none"
              value={filterDir} onChange={(e) => setFilterDir(e.target.value)}>
              {DIRECTIONS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted uppercase tracking-wider">Strategy</label>
            <select className="mt-1 w-full bg-bg border border-bg-border rounded px-2 py-1.5 text-[12px] text-white outline-none"
              value={filterStrat} onChange={(e) => setFilterStrat(e.target.value)}>
              <option>All</option>
              {STRATEGIES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted uppercase tracking-wider">Min Confidence {minConf}%</label>
            <input type="range" min={40} max={95} step={5}
              className="mt-2 w-full accent-brand"
              value={minConf} onChange={(e) => setMinConf(Number(e.target.value))} />
          </div>
        </div>
      )}

      {/* Strategy legend */}
      <StrategyLegend />

      {/* Setups grid */}
      {visible.length === 0 ? (
        <div className="card p-12 flex flex-col items-center gap-3 text-center">
          {scanning ? (
            <>
              <RefreshCw size={28} className="text-brand animate-spin" />
              <div className="text-sm text-muted">Scanning {SYMBOLS.length - 1} symbols across 3 timeframes…</div>
            </>
          ) : (
            <>
              <Bell size={28} className="text-muted" />
              <div className="text-sm text-white">No setups match current filters</div>
              <div className="text-[11px] text-muted max-w-xs">
                The scanner checks EURUSD, GBPUSD, USDJPY, XAUUSD, GBPJPY, AUDUSD &amp; EURJPY
                on M15, H1, H4. Click "Scan Now" to refresh.
              </div>
              <button onClick={() => load(true)}
                className="mt-2 px-4 py-1.5 bg-brand/20 text-brand border border-brand/40 rounded text-[12px]">
                Scan Now
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {visible.map((s) => (
            <div key={s.id} id={`setup-${s.id}`}>
              <SetupCard
                setup={s}
                onDismiss={handleDismiss}
                onTrade={handleTrade}
                highlighted={highlightId === s.id}
              />
            </div>
          ))}
        </div>
      )}

      {/* Trade confirmation modal */}
      {tradeSetup && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-sm p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-base font-semibold text-white">Confirm Trade</div>
              <button onClick={() => setTradeSetup(null)} className="text-muted hover:text-white">✕</button>
            </div>
            {tradePlaced ? (
              <div className="text-center py-6 space-y-2">
                <div className="text-3xl">✅</div>
                <div className="text-sm text-bull font-semibold">Trade Placed Successfully</div>
                <button onClick={() => setTradeSetup(null)}
                  className="mt-3 px-6 py-2 bg-brand/20 text-brand border border-brand/40 rounded text-sm">
                  Close
                </button>
              </div>
            ) : (
              <>
                <div className={`p-3 rounded-lg border text-[12px] space-y-1.5 ${
                  tradeSetup.direction === "buy"
                    ? "border-bull/30 bg-bull/5"
                    : "border-bear/30 bg-bear/5"
                }`}>
                  <div className="flex justify-between"><span className="text-muted">Symbol</span><span className="text-white font-bold">{tradeSetup.symbol}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Direction</span><span className={tradeSetup.direction === "buy" ? "text-bull font-bold" : "text-bear font-bold"}>{tradeSetup.direction.toUpperCase()}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Entry</span><span className="text-white font-mono">{tradeSetup.entry_price.toFixed(5)}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Stop Loss</span><span className="text-bear font-mono">{tradeSetup.stop_loss.toFixed(5)}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Take Profit</span><span className="text-bull font-mono">{tradeSetup.take_profit_2.toFixed(5)}</span></div>
                  <div className="flex justify-between"><span className="text-muted">R:R</span><span className="text-white">{tradeSetup.rr_ratio}:1</span></div>
                  <div className="flex justify-between"><span className="text-muted">Volume</span><span className="text-white">0.01 lots</span></div>
                </div>
                <div className="text-[10px] text-muted bg-yellow-500/5 border border-yellow-500/20 rounded p-2">
                  ⚠ Trade will be placed on your connected MT5 account. Adjust volume in the Trades page.
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setTradeSetup(null)}
                    className="flex-1 py-2 border border-bg-border text-muted rounded text-sm hover:text-white transition-colors">
                    Cancel
                  </button>
                  <button onClick={confirmTrade}
                    className={`flex-1 py-2 rounded text-sm font-semibold transition-colors ${
                      tradeSetup.direction === "buy"
                        ? "bg-bull/20 hover:bg-bull/30 text-bull border border-bull/40"
                        : "bg-bear/20 hover:bg-bear/30 text-bear border border-bear/40"
                    }`}>
                    Place {tradeSetup.direction.toUpperCase()}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
