import { useEffect, useState } from "react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown, Activity, Target, Percent, DollarSign } from "lucide-react";
import { api } from "../lib/api";
import { useLive } from "../hooks/useLive";

const fmt2 = (n: number) => n?.toFixed(2) ?? "—";
const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n?.toFixed(1)}%`;

function KpiCard({
  label, value, sub, icon: Icon, color = "text-white",
}: {
  label: string; value: string | number; sub?: string;
  icon: any; color?: string;
}) {
  return (
    <div className="card p-4 flex gap-4 items-start">
      <div className="p-2 rounded-lg bg-brand/10 border border-brand/20 shrink-0">
        <Icon size={18} className="text-brand" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] text-muted uppercase tracking-wider mb-1">{label}</div>
        <div className={`text-xl font-semibold ${color}`}>{value}</div>
        {sub && <div className="text-[11px] text-subtle mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-[11px] space-y-0.5">
      <div className="text-muted">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color }}>{p.name}: {fmt2(p.value)}</div>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const { tick } = useLive();
  const [stats, setStats] = useState<any>(null);
  const [equity, setEquity] = useState<any[]>([]);
  const [forecast, setForecast] = useState<any>(null);
  const [perf, setPerf] = useState<any[]>([]);
  const [scan, setScan] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const [s, eq, f, p, sc] = await Promise.all([
        api.walletStats().catch(() => null),
        api.equityCurve(30).catch(() => []),
        api.growthForecast(30).catch(() => null),
        api.recentPerf(7).catch(() => []),
        api.multiScan("EURUSD,GBPUSD,USDJPY,XAUUSD").catch(() => []),
      ]);
      setStats(s);
      setEquity(eq);
      setForecast(f);
      setPerf(p);
      setScan(sc);
    };
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const balance = tick?.account?.balance ?? stats?.account?.balance ?? 0;
  const equity_ = tick?.account?.equity ?? stats?.account?.equity ?? 0;
  const totals = stats?.totals ?? {};

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        <span className="text-[11px] text-muted">Auto-refresh 15s</span>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Balance" value={`$${balance.toLocaleString()}`}
          sub={`Equity $${equity_.toFixed(2)}`} icon={DollarSign} />
        <KpiCard label="Total Profit" value={`$${fmt2(totals.total_profit ?? 0)}`}
          sub={`${totals.total_pips ?? 0} pips`} icon={TrendingUp}
          color={(totals.total_profit ?? 0) >= 0 ? "text-bull" : "text-bear"} />
        <KpiCard label="Win Rate" value={`${totals.win_rate ?? 0}%`}
          sub={`${totals.wins ?? 0}W / ${totals.losses ?? 0}L`} icon={Percent}
          color={(totals.win_rate ?? 0) >= 50 ? "text-bull" : "text-bear"} />
        <KpiCard label="Profit Factor" value={fmt2(totals.profit_factor ?? 0)}
          sub={`${totals.total_trades ?? 0} closed trades`} icon={Target}
          color={(totals.profit_factor ?? 0) >= 1 ? "text-bull" : "text-bear"} />
      </div>

      {/* Equity curve + forecast */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-white">Equity Curve</span>
            {forecast && (
              <span className={`text-[11px] font-semibold ${
                forecast.projected_return_pct >= 0 ? "text-bull" : "text-bear"
              }`}>
                30d forecast {fmtPct(forecast.projected_return_pct)}
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={equity.length > 0 ? equity : [{ date: "now", equity: balance }]}
              margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2962ff" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2962ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" />
              <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }}
                tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="equity" name="Equity"
                stroke="#2962ff" fill="url(#eqGrad)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="balance" name="Balance"
                stroke="#26a69a" fill="none" strokeWidth={1.5}
                strokeDasharray="4 2" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
          {/* Forecast overlay */}
          {forecast?.forecast?.length > 0 && (
            <div className="mt-2 text-[10px] text-muted">
              Projected in 30 days: <span className="text-white font-semibold">
                ${forecast.projected_balance.toLocaleString()}
              </span>
              {" "}· confidence {(forecast.confidence * 100).toFixed(0)}%
            </div>
          )}
        </div>

        {/* Daily P&L */}
        <div className="card p-4">
          <div className="text-sm font-medium text-white mb-3">Daily P&amp;L (7d)</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={perf} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 9 }}
                tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#374151" />
              <Bar dataKey="profit" name="Profit"
                fill="#26a69a" radius={[3, 3, 0, 0]}
                label={false}
                /* color negative bars red */
                // @ts-ignore
                isAnimationActive={false}
              >
                {perf.map((entry, i) => (
                  <rect key={i} fill={entry.profit >= 0 ? "#26a69a" : "#ef5350"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Market scan */}
      <div className="card p-4">
        <div className="text-sm font-medium text-white mb-3">Market Scan</div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-muted text-[10px] uppercase border-b border-bg-border">
                <th className="text-left pb-2">Symbol</th>
                <th className="text-right pb-2">Bid</th>
                <th className="text-right pb-2">Signal</th>
                <th className="text-right pb-2">Score</th>
                <th className="text-right pb-2">RSI</th>
                <th className="text-right pb-2">MACD</th>
                <th className="text-right pb-2">Trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bg-border">
              {scan.map((row) => (
                <tr key={row.symbol} className="hover:bg-white/5">
                  <td className="py-2 font-semibold text-white">{row.symbol}</td>
                  <td className="py-2 text-right font-mono">
                    {row.bid?.toFixed(row.symbol.includes("JPY") ? 3 : 5) ?? "—"}
                  </td>
                  <td className="py-2 text-right">
                    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                      row.direction === "buy"
                        ? "bg-bull/20 text-bull border border-bull/30"
                        : row.direction === "sell"
                        ? "bg-bear/20 text-bear border border-bear/30"
                        : "bg-yellow-500/10 text-yellow-400 border border-yellow-400/20"
                    }`}>{row.direction ?? "—"}</span>
                  </td>
                  <td className="py-2 text-right font-mono">
                    <span className={row.score >= 0 ? "text-bull" : "text-bear"}>
                      {row.score?.toFixed(3) ?? "—"}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono">
                    <span className={
                      row.rsi < 30 ? "text-bull" : row.rsi > 70 ? "text-bear" : "text-white"
                    }>{row.rsi?.toFixed(1) ?? "—"}</span>
                  </td>
                  <td className="py-2 text-right font-mono">
                    <span className={row.macd_hist >= 0 ? "text-bull" : "text-bear"}>
                      {row.macd_hist?.toFixed(5) ?? "—"}
                    </span>
                  </td>
                  <td className="py-2 text-right">
                    {row.above_ema200
                      ? <span className="text-bull">↑ Bull</span>
                      : <span className="text-bear">↓ Bear</span>}
                  </td>
                </tr>
              ))}
              {scan.length === 0 && (
                <tr><td colSpan={7} className="py-6 text-center text-muted">Loading market data…</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
