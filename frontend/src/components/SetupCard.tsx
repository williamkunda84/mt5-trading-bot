/**
 * SetupCard
 * Rich card showing a single trade setup: entry, SL, TP1/TP2/TP3,
 * confidence ring, strategy badges, and countdown timer.
 */
import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Clock, Target, Shield,
  ChevronDown, ChevronUp, X,
} from "lucide-react";
import { api } from "../lib/api";

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
  strategy_details: Array<{
    name: string;
    confidence: number;
    notes: string;
    eta_minutes: number | null;
  }>;
  status: string;
  eta_minutes: number | null;
  detected_at: string;
  notes: string;
}

interface Props {
  setup: Setup;
  onDismiss: (id: string) => void;
  onTrade?: (setup: Setup) => void;
  highlighted?: boolean;
}

// Strategy colour map
const STRATEGY_COLORS: Record<string, string> = {
  "EMA Confluence":     "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "RSI Divergence":     "bg-purple-500/20 text-purple-400 border-purple-500/30",
  "MACD Crossover":     "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  "BB Squeeze Breakout":"bg-orange-500/20 text-orange-400 border-orange-500/30",
  "S/R Bounce":         "bg-pink-500/20 text-pink-400 border-pink-500/30",
  "ICT Session Play":   "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  "Fibonacci":          "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  "Candlestick Pattern":"bg-rose-500/20 text-rose-400 border-rose-500/30",
};

function ConfidenceRing({ pct }: { pct: number }) {
  const r = 20;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = pct >= 75 ? "#26a69a" : pct >= 55 ? "#f59e0b" : "#ef5350";
  return (
    <svg width={52} height={52} viewBox="0 0 52 52" className="shrink-0">
      <circle cx={26} cy={26} r={r} fill="none" stroke="#1e2336" strokeWidth={5} />
      <circle cx={26} cy={26} r={r} fill="none" stroke={color} strokeWidth={5}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 26 26)"
      />
      <text x={26} y={30} textAnchor="middle" fontSize={11} fontWeight="bold" fill={color}>
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

function Countdown({ eta, detectedAt }: { eta: number | null; detectedAt: string }) {
  const [secs, setSecs] = useState<number | null>(null);

  useEffect(() => {
    if (eta === null || eta === 0) { setSecs(null); return; }
    // Calculate remaining seconds based on detected_at + eta_minutes
    const target = new Date(detectedAt).getTime() + eta * 60_000;
    const tick = () => {
      const left = Math.max(0, Math.round((target - Date.now()) / 1000));
      setSecs(left);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [eta, detectedAt]);

  if (eta === 0 || secs === null)
    return <span className="text-[10px] text-yellow-400 font-bold bg-yellow-400/10 px-2 py-0.5 rounded-full border border-yellow-400/30">CONFIRMED</span>;

  const mins = Math.floor(secs / 60);
  const s = secs % 60;
  const urgent = mins < 15;
  return (
    <span className={`flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
      urgent
        ? "text-orange-400 bg-orange-400/10 border-orange-400/30 animate-pulse"
        : "text-white/60 bg-white/5 border-white/10"
    }`}>
      <Clock size={9} />
      {mins}:{String(s).padStart(2, "0")}
    </span>
  );
}

function PriceLine({
  label, price, color, barPct,
}: { label: string; price: number; color: string; barPct: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`text-[10px] w-6 font-bold ${color}`}>{label}</span>
      <div className="flex-1 h-1 bg-bg-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color.replace("text-", "bg-")}`}
          style={{ width: `${Math.max(2, Math.min(100, barPct))}%` }} />
      </div>
      <span className="text-[11px] font-mono text-white w-20 text-right">{price.toFixed(5)}</span>
    </div>
  );
}

export default function SetupCard({ setup, onDismiss, onTrade, highlighted }: Props) {
  const [expanded, setExpanded] = useState(false);
  const isBuy = setup.direction === "buy";

  const dirColor = isBuy ? "text-bull" : "text-bear";
  const dirBg = isBuy ? "bg-bull/10 border-bull/30" : "bg-bear/10 border-bear/30";

  // Build normalised bar widths for price levels
  const allPrices = [setup.stop_loss, setup.entry_price, setup.take_profit_1, setup.take_profit_2, setup.take_profit_3];
  const minP = Math.min(...allPrices);
  const maxP = Math.max(...allPrices);
  const norm = (p: number) => maxP > minP ? ((p - minP) / (maxP - minP)) * 100 : 50;

  return (
    <div className={`card flex flex-col gap-0 overflow-hidden transition-all ${
      highlighted ? "ring-1 ring-yellow-400/50" : ""
    }`}>
      {/* Header */}
      <div className={`px-4 py-3 flex items-center justify-between border-b border-bg-border`}>
        <div className="flex items-center gap-3">
          <div className={`p-1.5 rounded-lg border ${dirBg}`}>
            {isBuy ? <TrendingUp size={14} className={dirColor} /> : <TrendingDown size={14} className={dirColor} />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white">{setup.symbol}</span>
              <span className="text-[10px] text-muted border border-bg-border rounded px-1.5 py-0.5">{setup.timeframe}</span>
              <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${dirBg} ${dirColor}`}>
                {setup.direction}
              </span>
            </div>
            <div className="text-[10px] text-muted mt-0.5">
              R:R {setup.rr_ratio}:1 · {setup.strategies_confirmed.length} strategies
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Countdown eta={setup.eta_minutes} detectedAt={setup.detected_at} />
          <ConfidenceRing pct={setup.confidence} />
          <button onClick={() => onDismiss(setup.id)} className="text-muted hover:text-bear transition-colors">
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Price levels */}
      <div className="px-4 py-3 space-y-1.5 border-b border-bg-border">
        <PriceLine label="SL"  price={setup.stop_loss}    color="text-bear"          barPct={norm(setup.stop_loss)} />
        <PriceLine label="In"  price={setup.entry_price}  color="text-white"         barPct={norm(setup.entry_price)} />
        <PriceLine label="TP1" price={setup.take_profit_1} color="text-bull"         barPct={norm(setup.take_profit_1)} />
        <PriceLine label="TP2" price={setup.take_profit_2} color="text-emerald-400"  barPct={norm(setup.take_profit_2)} />
        <PriceLine label="TP3" price={setup.take_profit_3} color="text-cyan-400"     barPct={norm(setup.take_profit_3)} />
      </div>

      {/* Strategy badges */}
      <div className="px-4 py-2.5 flex flex-wrap gap-1.5 border-b border-bg-border">
        {setup.strategies_confirmed.map((name) => (
          <span key={name} className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded border ${
            STRATEGY_COLORS[name] ?? "bg-white/5 text-white/50 border-white/10"
          }`}>
            {name}
          </span>
        ))}
      </div>

      {/* Expand / collapse detailed breakdown */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="px-4 py-1.5 flex items-center justify-between text-[10px] text-muted hover:text-white transition-colors w-full"
      >
        <span>Strategy breakdown</span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2 border-t border-bg-border pt-2">
          {setup.strategy_details.map((s) => (
            <div key={s.name} className="space-y-0.5">
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-semibold ${STRATEGY_COLORS[s.name]?.split(" ")[1] ?? "text-white"}`}>
                  {s.name}
                </span>
                <div className="flex items-center gap-2">
                  {s.eta_minutes !== null && s.eta_minutes !== undefined && (
                    <span className="text-[9px] text-white/40">
                      {s.eta_minutes === 0 ? "confirmed" : `~${s.eta_minutes}m`}
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-white">{s.confidence.toFixed(0)}%</span>
                </div>
              </div>
              <div className="h-1 bg-bg rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${STRATEGY_COLORS[s.name]?.split(" ")[0] ?? "bg-white/20"}`}
                  style={{ width: `${s.confidence}%` }}
                />
              </div>
              <p className="text-[9px] text-muted leading-relaxed">{s.notes}</p>
            </div>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div className="px-4 py-2.5 flex gap-2 border-t border-bg-border bg-bg/40">
        <button
          onClick={() => onTrade?.(setup)}
          className={`flex-1 py-1.5 rounded text-[11px] font-semibold transition-colors ${
            isBuy
              ? "bg-bull/20 hover:bg-bull/30 text-bull border border-bull/40"
              : "bg-bear/20 hover:bg-bear/30 text-bear border border-bear/40"
          }`}
        >
          {isBuy ? "▲ Trade Setup BUY" : "▼ Trade Setup SELL"}
        </button>
      </div>
    </div>
  );
}
