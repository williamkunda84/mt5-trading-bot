import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";
import { api } from "../lib/api";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-[11px] space-y-0.5">
      <div className="text-muted">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</div>
      ))}
    </div>
  );
};

export default function History() {
  const [stats, setStats] = useState<any>(null);
  const [perf, setPerf] = useState<any[]>([]);
  const [forecast, setForecast] = useState<any>(null);
  const [forecastDays, setForecastDays] = useState(30);
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const [s, p, f, t] = await Promise.all([
        api.walletStats().catch(() => null),
        api.recentPerf(30).catch(() => []),
        api.growthForecast(forecastDays).catch(() => null),
        api.listTrades("closed").catch(() => []),
      ]);
      setStats(s);
      setPerf(p);
      setForecast(f);
      setTrades(t.slice(0, 50));
    };
    load();
  }, [forecastDays]);

  const totals = stats?.totals ?? {};
  const bySymbol = stats?.by_symbol ?? {};

  // Symbol performance bar data
  const symData = Object.entries(bySymbol).map(([sym, d]: [string, any]) => ({
    symbol: sym,
    profit: d.profit,
    win_rate: d.win_rate,
    trades: d.wins + d.losses,
  }));

  return (
    <div className="p-5 space-y-5">
      <h1 className="text-lg font-semibold text-white">Trade History &amp; Analytics</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Closed", value: totals.total_trades ?? 0, color: "text-white" },
          { label: "Win Rate", value: `${totals.win_rate ?? 0}%`, color: (totals.win_rate ?? 0) >= 50 ? "text-bull" : "text-bear" },
          { label: "Total Pips", value: `${totals.total_pips ?? 0}`, color: (totals.total_pips ?? 0) >= 0 ? "text-bull" : "text-bear" },
          { label: "Profit Factor", value: totals.profit_factor ?? 0, color: (totals.profit_factor ?? 0) >= 1 ? "text-bull" : "text-bear" },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</div>
            <div className={`text-xl font-semibold font-mono ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* 30-day P&L + forecast */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="text-sm font-medium text-white mb-3">30-Day P&amp;L</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={perf} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 9 }}
                tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="profit" name="Profit" radius={[2, 2, 0, 0]}>
                {perf.map((entry, i) => (
                  <Cell key={i} fill={entry.profit >= 0 ? "#26a69a" : "#ef5350"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-white">Growth Forecast</div>
            <div className="flex gap-1">
              {[7, 14, 30, 60, 90].map((d) => (
                <button key={d} onClick={() => setForecastDays(d)}
                  className={`px-1.5 py-0.5 rounded text-[10px] transition-colors ${
                    d === forecastDays ? "bg-brand text-white" : "text-muted hover:text-white"
                  }`}>{d}d</button>
              ))}
            </div>
          </div>
          {forecast?.forecast ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <LineChart data={forecast.forecast} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" />
                  <XAxis dataKey="day" tick={{ fill: "#6b7280", fontSize: 9 }}
                    tickFormatter={(v) => `d${v}`} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} domain={["auto", "auto"]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="balance" name="Projected"
                    stroke="#2962ff" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-2 grid grid-cols-3 gap-2 text-[10px]">
                <div className="text-muted">Projected Return
                  <div className={`font-semibold text-sm ${forecast.projected_return_pct >= 0 ? "text-bull" : "text-bear"}`}>
                    {forecast.projected_return_pct >= 0 ? "+" : ""}{forecast.projected_return_pct}%
                  </div>
                </div>
                <div className="text-muted">Final Balance
                  <div className="font-semibold text-sm text-white">${forecast.projected_balance?.toLocaleString()}</div>
                </div>
                <div className="text-muted">Confidence
                  <div className="font-semibold text-sm text-white">{(forecast.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
            </>
          ) : <div className="h-36 flex items-center justify-center text-muted text-sm">Loading…</div>}
        </div>
      </div>

      {/* Per-symbol breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="text-sm font-medium text-white mb-3">Profit by Symbol</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={symData} layout="vertical" margin={{ top: 4, right: 4, left: 40, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2336" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis dataKey="symbol" type="category" tick={{ fill: "#9ca3af", fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="profit" name="Profit" radius={[0, 3, 3, 0]}>
                {symData.map((entry, i) => (
                  <Cell key={i} fill={entry.profit >= 0 ? "#26a69a" : "#ef5350"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <div className="text-sm font-medium text-white mb-3">Win Rate by Symbol</div>
          <div className="space-y-2">
            {symData.map((d) => (
              <div key={d.symbol}>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-subtle">{d.symbol}</span>
                  <span className="text-white">{d.win_rate}% <span className="text-muted">({d.trades})</span></span>
                </div>
                <div className="h-2 bg-bg rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${d.win_rate >= 50 ? "bg-bull" : "bg-bear"}`}
                    style={{ width: `${d.win_rate}%` }}
                  />
                </div>
              </div>
            ))}
            {symData.length === 0 && <div className="text-muted text-sm py-4">No closed trades yet</div>}
          </div>
        </div>
      </div>

      {/* Recent closed trades */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-bg-border text-sm font-medium text-white">
          Recent Closed Trades
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-muted text-[10px] uppercase border-b border-bg-border">
                <th className="text-left px-4 py-2">Symbol</th>
                <th className="text-center px-2 py-2">Type</th>
                <th className="text-right px-3 py-2">Open</th>
                <th className="text-right px-3 py-2">Close</th>
                <th className="text-right px-3 py-2">Profit</th>
                <th className="text-right px-3 py-2">Pips</th>
                <th className="text-right px-3 py-2">Result</th>
                <th className="text-right px-3 py-2">Closed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bg-border">
              {trades.map((t) => (
                <tr key={t.id} className="hover:bg-white/5">
                  <td className="px-4 py-2 font-semibold text-white">{t.symbol}</td>
                  <td className="px-2 py-2 text-center">
                    <span className={t.order_type === "buy" ? "text-bull" : "text-bear"}>
                      {t.order_type?.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{t.open_price?.toFixed(5)}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.close_price?.toFixed(5) ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    <span className={t.profit >= 0 ? "text-bull" : "text-bear"}>
                      {t.profit >= 0 ? "+" : ""}${t.profit?.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    <span className={t.pips >= 0 ? "text-bull" : "text-bear"}>
                      {t.pips >= 0 ? "+" : ""}{t.pips?.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-[10px]">
                    <span className={`uppercase font-bold ${t.notes === "tp_hit" ? "text-bull" : t.notes === "sl_hit" ? "text-bear" : "text-muted"}`}>
                      {t.notes === "tp_hit" ? "TP" : t.notes === "sl_hit" ? "SL" : t.notes ?? "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-muted">
                    {t.closed_at ? new Date(t.closed_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
              {trades.length === 0 && (
                <tr><td colSpan={8} className="py-10 text-center text-muted">No closed trades yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
