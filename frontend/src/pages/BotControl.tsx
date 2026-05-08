import { useEffect, useState } from "react";
import { Play, Square, Settings, AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { api } from "../lib/api";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];
const DEFAULT_SYMBOLS = "EURUSD,GBPUSD,USDJPY,XAUUSD";

function SignalCard({ symbol, signal }: { symbol: string; signal: any }) {
  const dir = signal.direction;
  const score = signal.score ?? 0;
  const sub = signal.sub_scores ?? {};
  const pct = Math.abs(score) * 100;

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-white">{symbol}</span>
        <span className={`text-[11px] font-bold uppercase px-2 py-0.5 rounded border ${
          dir === "buy"
            ? "text-bull border-bull/40 bg-bull/10"
            : dir === "sell"
            ? "text-bear border-bear/40 bg-bear/10"
            : "text-yellow-400 border-yellow-400/30 bg-yellow-400/5"
        }`}>{dir}</span>
      </div>

      {/* Score bar */}
      <div>
        <div className="flex justify-between text-[10px] text-muted mb-1">
          <span>AI Score</span>
          <span className={score >= 0 ? "text-bull" : "text-bear"}>
            {score >= 0 ? "+" : ""}{score.toFixed(3)}
          </span>
        </div>
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full signal-bar ${dir === "buy" ? "bg-bull" : dir === "sell" ? "bg-bear" : "bg-yellow-500"}`}
            style={{ width: `${pct}%`, marginLeft: dir === "sell" ? `${100 - pct}%` : undefined }}
          />
        </div>
      </div>

      {/* Sub-signals */}
      <div className="space-y-1">
        {Object.entries(sub).map(([k, v]: [string, any]) => (
          <div key={k} className="flex items-center justify-between text-[10px]">
            <span className="text-muted capitalize">{k}</span>
            <div className="flex items-center gap-1.5">
              <div className="w-16 h-1 bg-bg rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${v >= 0 ? "bg-bull" : "bg-bear"}`}
                  style={{ width: `${Math.abs(v) * 100}%` }}
                />
              </div>
              <span className={v >= 0 ? "text-bull" : "text-bear"}>{v.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Indicator snapshot */}
      {signal.indicators && (
        <div className="grid grid-cols-3 gap-1 text-[10px] pt-1 border-t border-bg-border">
          <div className="text-muted">RSI <span className="text-white">{signal.indicators.rsi?.toFixed(1)}</span></div>
          <div className="text-muted">MACD <span className={signal.indicators.macd >= 0 ? "text-bull" : "text-bear"}>
            {signal.indicators.macd?.toFixed(5)}</span></div>
          <div className="text-muted">ATR <span className="text-white">{signal.indicators.atr?.toFixed(5)}</span></div>
        </div>
      )}
    </div>
  );
}

export default function BotControl() {
  const [status, setStatus] = useState<any>(null);
  const [signals, setSignals] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [cfg, setCfg] = useState({
    symbols: DEFAULT_SYMBOLS,
    risk_percent: 1.5,
    max_open_trades: 5,
    timeframe: "H1",
  });

  const load = async () => {
    const [s, sig] = await Promise.all([
      api.botStatus().catch(() => null),
      api.botSignals().catch(() => ({})),
    ]);
    setStatus(s);
    setSignals(sig ?? {});
    if (s?.config) {
      setCfg({
        symbols: s.config.symbols ?? DEFAULT_SYMBOLS,
        risk_percent: s.config.risk_percent ?? 1.5,
        max_open_trades: s.config.max_open_trades ?? 5,
        timeframe: s.config.timeframe ?? "H1",
      });
    }
  };

  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, []);

  const toggle = async () => {
    setLoading(true);
    try {
      if (status?.is_running) await api.botStop();
      else await api.botStart();
      await load();
    } finally { setLoading(false); }
  };

  const saveConfig = async () => {
    await api.botUpdateConfig(cfg);
    await load();
  };

  const running = status?.is_running ?? false;

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Bot Control</h1>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`w-2 h-2 rounded-full ${running ? "bg-bull animate-pulse" : "bg-bear"}`} />
          <span className={running ? "text-bull" : "text-bear"}>{running ? "Running" : "Stopped"}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Start/Stop */}
        <div className="card p-5 flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl border ${running
              ? "bg-bull/10 border-bull/30"
              : "bg-bear/10 border-bear/30"
            }`}>
              {running
                ? <TrendingUp size={22} className="text-bull" />
                : <Minus size={22} className="text-bear" />
              }
            </div>
            <div>
              <div className="font-semibold text-white">Trading Bot</div>
              <div className="text-[11px] text-muted">
                {running ? `Tick #${status?.runtime?.tick_count ?? 0}` : "Idle"}
              </div>
            </div>
          </div>

          <button
            onClick={toggle}
            disabled={loading}
            className={`w-full flex items-center justify-center gap-2 py-3 rounded-lg font-semibold text-sm transition-all ${
              running
                ? "bg-bear/20 hover:bg-bear/30 text-bear border border-bear/40"
                : "bg-bull/20 hover:bg-bull/30 text-bull border border-bull/40"
            } disabled:opacity-50`}
          >
            {running ? <><Square size={15} /> Stop Bot</> : <><Play size={15} /> Start Bot</>}
          </button>

          {status?.runtime?.errors?.length > 0 && (
            <div className="text-[10px] text-bear flex gap-1 items-start">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              {status.runtime.errors[0]}
            </div>
          )}
        </div>

        {/* Config */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Settings size={15} /> Configuration
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider">Symbols (comma-separated)</label>
              <input
                className="mt-1 w-full bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white focus:border-brand/60 outline-none"
                value={cfg.symbols}
                onChange={(e) => setCfg({ ...cfg, symbols: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] text-muted uppercase tracking-wider">Risk %</label>
                <input type="number" step={0.1} min={0.1} max={10}
                  className="mt-1 w-full bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white focus:border-brand/60 outline-none"
                  value={cfg.risk_percent}
                  onChange={(e) => setCfg({ ...cfg, risk_percent: parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <label className="text-[10px] text-muted uppercase tracking-wider">Max Trades</label>
                <input type="number" min={1} max={20}
                  className="mt-1 w-full bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white focus:border-brand/60 outline-none"
                  value={cfg.max_open_trades}
                  onChange={(e) => setCfg({ ...cfg, max_open_trades: parseInt(e.target.value) })}
                />
              </div>
              <div>
                <label className="text-[10px] text-muted uppercase tracking-wider">Timeframe</label>
                <select
                  className="mt-1 w-full bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white focus:border-brand/60 outline-none"
                  value={cfg.timeframe}
                  onChange={(e) => setCfg({ ...cfg, timeframe: e.target.value })}
                >
                  {TIMEFRAMES.map((tf) => <option key={tf}>{tf}</option>)}
                </select>
              </div>
            </div>

            <button
              onClick={saveConfig}
              className="w-full py-2 bg-brand/20 hover:bg-brand/30 text-brand border border-brand/40 rounded text-sm transition-colors"
            >
              Save Configuration
            </button>
          </div>
        </div>
      </div>

      {/* Live signals */}
      <div>
        <div className="text-sm font-medium text-white mb-3">Live AI Signals</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(signals).map(([sym, sig]) => (
            <SignalCard key={sym} symbol={sym} signal={sig} />
          ))}
          {Object.keys(signals).length === 0 && (
            <div className="col-span-full text-center text-muted py-8 text-sm">
              Start the bot to see live signals
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
