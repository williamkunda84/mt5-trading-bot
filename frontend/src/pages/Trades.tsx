import { useEffect, useState } from "react";
import { Plus, X, RefreshCw } from "lucide-react";
import { api } from "../lib/api";

const SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY", "AUDUSD", "USDCAD"];

function Badge({ status }: { status: string }) {
  const cls = status === "open"
    ? "text-brand border-brand/40 bg-brand/10"
    : status === "closed" && status.includes("tp")
    ? "text-bull border-bull/40 bg-bull/10"
    : "text-subtle border-bg-border bg-bg";
  return (
    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${cls}`}>
      {status}
    </span>
  );
}

export default function Trades() {
  const [trades, setTrades] = useState<any[]>([]);
  const [filter, setFilter] = useState<"open" | "closed" | "all">("open");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ symbol: "EURUSD", order_type: "buy", volume: 0.01 });
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const t = await api.listTrades(filter === "all" ? undefined : filter).catch(() => []);
    setTrades(t);
  };

  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, [filter]);

  const placeTrade = async () => {
    setLoading(true);
    try { await api.manualTrade(form); setShowForm(false); await load(); }
    finally { setLoading(false); }
  };

  const closeTrade = async (id: string) => {
    await api.closeTrade(id);
    await load();
  };

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-white">Trades</h1>
        <div className="flex gap-1 ml-2">
          {(["open", "closed", "all"] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-[11px] transition-colors capitalize ${
                f === filter ? "bg-brand text-white" : "text-muted hover:text-white"
              }`}>{f}</button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          <button onClick={load} className="p-1.5 text-muted hover:text-white">
            <RefreshCw size={14} />
          </button>
          <button onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand/20 hover:bg-brand/30 text-brand border border-brand/40 rounded text-[12px] transition-colors">
            <Plus size={13} /> Manual Trade
          </button>
        </div>
      </div>

      {/* Manual trade form */}
      {showForm && (
        <div className="card p-4 space-y-3">
          <div className="text-sm font-medium text-white">Place Manual Trade</div>
          <div className="flex gap-3 flex-wrap">
            <div>
              <label className="text-[10px] text-muted">Symbol</label>
              <select className="mt-1 block bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white outline-none"
                value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}>
                {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted">Type</label>
              <select className="mt-1 block bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white outline-none"
                value={form.order_type} onChange={(e) => setForm({ ...form, order_type: e.target.value })}>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted">Volume (lots)</label>
              <input type="number" step={0.01} min={0.01}
                className="mt-1 block bg-bg border border-bg-border rounded px-3 py-1.5 text-[12px] text-white outline-none w-24"
                value={form.volume} onChange={(e) => setForm({ ...form, volume: parseFloat(e.target.value) })} />
            </div>
            <div className="flex items-end gap-2">
              <button onClick={placeTrade} disabled={loading}
                className={`px-4 py-1.5 rounded text-sm font-semibold transition-colors ${
                  form.order_type === "buy"
                    ? "bg-bull/20 text-bull border border-bull/40"
                    : "bg-bear/20 text-bear border border-bear/40"
                } disabled:opacity-50`}>
                {loading ? "…" : `Place ${form.order_type.toUpperCase()}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trades table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-muted text-[10px] uppercase border-b border-bg-border bg-bg">
                <th className="text-left px-4 py-2">Symbol</th>
                <th className="text-center px-2 py-2">Type</th>
                <th className="text-right px-3 py-2">Vol</th>
                <th className="text-right px-3 py-2">Open</th>
                <th className="text-right px-3 py-2">Close</th>
                <th className="text-right px-3 py-2">SL</th>
                <th className="text-right px-3 py-2">TP</th>
                <th className="text-right px-3 py-2">Profit</th>
                <th className="text-right px-3 py-2">Pips</th>
                <th className="text-center px-3 py-2">Score</th>
                <th className="text-center px-2 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-bg-border">
              {trades.map((t) => (
                <tr key={t.id} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-2 font-semibold text-white">{t.symbol}</td>
                  <td className="px-2 py-2 text-center">
                    <span className={t.order_type === "buy" ? "text-bull" : "text-bear"}>
                      {t.order_type?.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">{t.volume}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.open_price?.toFixed(5)}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.close_price?.toFixed(5) ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-bear">{t.stop_loss?.toFixed(5) ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-bull">{t.take_profit?.toFixed(5) ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {t.profit != null
                      ? <span className={t.profit >= 0 ? "text-bull" : "text-bear"}>
                          {t.profit >= 0 ? "+" : ""}${t.profit.toFixed(2)}
                        </span>
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {t.pips != null
                      ? <span className={t.pips >= 0 ? "text-bull" : "text-bear"}>
                          {t.pips >= 0 ? "+" : ""}{t.pips.toFixed(1)}
                        </span>
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-center font-mono text-[11px]">
                    {t.signal_score != null
                      ? <span className={t.signal_score >= 0 ? "text-bull" : "text-bear"}>
                          {t.signal_score.toFixed(3)}
                        </span>
                      : "—"}
                  </td>
                  <td className="px-2 py-2 text-center"><Badge status={t.status} /></td>
                  <td className="px-3 py-2">
                    {t.status === "open" && (
                      <button onClick={() => closeTrade(t.id)}
                        className="p-1 text-muted hover:text-bear transition-colors">
                        <X size={13} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {trades.length === 0 && (
                <tr><td colSpan={12} className="py-10 text-center text-muted">No trades found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
