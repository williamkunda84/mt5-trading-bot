import { useEffect, useState, useRef } from "react";
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area,
} from "recharts";
import { api } from "../lib/api";

const SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY", "AUDUSD"];
const TIMEFRAMES = ["M15", "M30", "H1", "H4", "D1"];

function ScoreGauge({ score }: { score: number }) {
  const pct = ((score + 1) / 2) * 100;
  const color = score > 0.3 ? "#26a69a" : score < -0.3 ? "#ef5350" : "#f59e0b";
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-24 h-12 overflow-hidden">
        <svg viewBox="0 0 100 50" className="w-full">
          <path d="M5 50 A45 45 0 0 1 95 50" stroke="#1e2336" strokeWidth="8" fill="none" />
          <path
            d="M5 50 A45 45 0 0 1 95 50"
            stroke={color}
            strokeWidth="8"
            fill="none"
            strokeDasharray={`${pct * 1.41} 141`}
          />
        </svg>
      </div>
      <div className="text-lg font-bold" style={{ color }}>
        {score >= 0 ? "+" : ""}{score.toFixed(3)}
      </div>
    </div>
  );
}

const CandleTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="card px-3 py-2 text-[10px] space-y-0.5">
      <div className="text-muted">{d.time?.slice(0, 16)}</div>
      <div className="text-white">O {d.open} H {d.high}</div>
      <div className="text-white">L {d.low} C {d.close}</div>
      {d.rsi !== undefined && <div className="text-yellow-400">RSI {d.rsi?.toFixed(1)}</div>}
    </div>
  );
};

export default function Analysis() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [tf, setTf] = useState("H1");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.analyze(symbol, tf);
      setData(d);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [symbol, tf]);

  const candles = data?.candles?.slice(-80) ?? [];
  const ind = data?.indicators ?? {};
  const sub = data?.sub_scores ?? {};

  // Build chart data with indicator overlays
  const chartData = candles.map((c: any, i: number) => ({
    ...c,
    time: c.time?.slice(5, 16),
    ema20: i < candles.length - 1 ? undefined : ind.ema20,
    ema50: i < candles.length - 1 ? undefined : ind.ema50,
    // For simplicity just show close line
    close_line: c.close,
  }));

  return (
    <div className="p-5 space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold text-white">Market Analysis</h1>
        <div className="flex gap-2 ml-auto">
          <select
            className="bg-bg-card border border-bg-border rounded px-3 py-1.5 text-[12px] text-white outline-none"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          >
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
          <div className="flex gap-1">
            {TIMEFRAMES.map((t) => (
              <button key={t}
                onClick={() => setTf(t)}
                className={`px-2 py-1 rounded text-[11px] transition-colors ${
                  t === tf ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-white"
                }`}
              >{t}</button>
            ))}
          </div>
          <button onClick={load}
            className="px-3 py-1 bg-brand/20 text-brand border border-brand/30 rounded text-[12px]">
            Refresh
          </button>
        </div>
      </div>

      {/* Score + sub-signals */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card p-4 flex flex-col items-center justify-center gap-2">
            <div className="text-[11px] text-muted uppercase tracking-wider">AI Score</div>
            <ScoreGauge score={data.score} />
            <span className={`text-sm font-bold uppercase px-3 py-1 rounded border ${
              data.direction === "buy"
                ? "text-bull border-bull/40 bg-bull/10"
                : data.direction === "sell"
                ? "text-bear border-bear/40 bg-bear/10"
                : "text-yellow-400 border-yellow-400/30 bg-yellow-400/5"
            }`}>{data.direction}</span>
          </div>

          <div className="card p-4 md:col-span-2">
            <div className="text-[11px] text-muted uppercase tracking-wider mb-3">Sub-Signal Breakdown</div>
            <div className="space-y-2">
              {Object.entries(sub).map(([k, v]: [string, any]) => (
                <div key={k} className="flex items-center gap-3">
                  <div className="w-20 text-[11px] text-muted capitalize shrink-0">{k}</div>
                  <div className="flex-1 h-2 bg-bg rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${v >= 0 ? "bg-bull" : "bg-bear"}`}
                      style={{
                        width: `${Math.abs(v) * 50}%`,
                        marginLeft: v < 0 ? `${50 - Math.abs(v) * 50}%` : "50%",
                      }}
                    />
                  </div>
                  <div className={`w-12 text-right text-[11px] font-mono ${v >= 0 ? "text-bull" : "text-bear"}`}>
                    {v >= 0 ? "+" : ""}{v.toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Price chart */}
      <div className="card p-4">
        <div className="text-sm font-medium text-white mb-1">{symbol} · {tf} · Price</div>
        {loading ? (
          <div className="h-56 flex items-center justify-center text-muted text-sm">Loading…</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" />
              <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} domain={["auto", "auto"]} />
              <Tooltip content={<CandleTooltip />} />
              <Area type="monotone" dataKey="close_line" name="Close"
                stroke="#2962ff" fill="#2962ff22" strokeWidth={1.5} dot={false} />
              {ind.bb_upper && <ReferenceLine y={ind.bb_upper} stroke="#f59e0b44" strokeDasharray="4 2" />}
              {ind.bb_lower && <ReferenceLine y={ind.bb_lower} stroke="#f59e0b44" strokeDasharray="4 2" />}
              {ind.ema20 && <ReferenceLine y={ind.ema20} stroke="#26a69a55" strokeDasharray="3 3" />}
              {ind.ema50 && <ReferenceLine y={ind.ema50} stroke="#2962ff55" strokeDasharray="3 3" />}
              {ind.support && <ReferenceLine y={ind.support} stroke="#26a69a77" label={{ value: "S", fill: "#26a69a", fontSize: 10 }} />}
              {ind.resistance && <ReferenceLine y={ind.resistance} stroke="#ef535077" label={{ value: "R", fill: "#ef5350", fontSize: 10 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Indicator grid */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "RSI (14)", value: ind.rsi?.toFixed(2), color: ind.rsi < 30 ? "text-bull" : ind.rsi > 70 ? "text-bear" : "text-white" },
            { label: "MACD", value: ind.macd?.toFixed(5), color: ind.macd >= 0 ? "text-bull" : "text-bear" },
            { label: "ATR", value: ind.atr?.toFixed(5), color: "text-white" },
            { label: "Stoch K", value: ind.stoch_k?.toFixed(1), color: ind.stoch_k < 20 ? "text-bull" : ind.stoch_k > 80 ? "text-bear" : "text-white" },
            { label: "EMA 20", value: ind.ema20?.toFixed(5), color: "text-white" },
            { label: "EMA 50", value: ind.ema50?.toFixed(5), color: "text-white" },
            { label: "BB Upper", value: ind.bb_upper?.toFixed(5), color: "text-yellow-400" },
            { label: "BB Lower", value: ind.bb_lower?.toFixed(5), color: "text-yellow-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="card p-3">
              <div className="text-[10px] text-muted uppercase tracking-wider">{label}</div>
              <div className={`text-sm font-mono font-semibold mt-1 ${color}`}>{value ?? "—"}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
