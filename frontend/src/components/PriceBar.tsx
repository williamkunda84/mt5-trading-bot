import { useLive } from "../hooks/useLive";

const SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "GBPJPY"];

export default function PriceBar() {
  const { tick } = useLive();

  return (
    <div className="h-9 bg-bg-card border-b border-bg-border flex items-center px-4 gap-6 overflow-x-auto shrink-0">
      {SYMBOLS.map((sym) => {
        const p = tick?.prices?.[sym];
        const sig = tick?.signals?.[sym];
        return (
          <div key={sym} className="flex items-center gap-2 shrink-0">
            <span className="text-[11px] text-muted font-semibold">{sym}</span>
            <span className="text-[12px] font-mono text-white">
              {p ? p.bid.toFixed(sym === "USDJPY" || sym === "GBPJPY" ? 3 : 5) : "—"}
            </span>
            {sig && (
              <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                sig.direction === "buy"
                  ? "bg-bull/20 text-bull border border-bull/30"
                  : sig.direction === "sell"
                  ? "bg-bear/20 text-bear border border-bear/30"
                  : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
              }`}>
                {sig.direction}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
