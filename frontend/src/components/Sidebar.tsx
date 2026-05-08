import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Bot, TrendingUp, History,
  BarChart2, Wifi, WifiOff,
} from "lucide-react";
import { useLive } from "../hooks/useLive";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/bot", label: "Bot Control", icon: Bot },
  { to: "/analysis", label: "Analysis", icon: BarChart2 },
  { to: "/trades", label: "Trades", icon: TrendingUp },
  { to: "/history", label: "History", icon: History },
];

export default function Sidebar() {
  const { tick, connected } = useLive();

  return (
    <aside className="w-56 shrink-0 flex flex-col bg-bg-card border-r border-bg-border h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-bg-border">
        <div className="flex items-center gap-2">
          <span className="text-2xl">📈</span>
          <div>
            <div className="text-sm font-semibold text-white">ForexBot</div>
            <div className="text-[10px] text-muted">AI Trading Engine</div>
          </div>
        </div>
      </div>

      {/* Live account */}
      {tick?.account && (
        <div className="px-4 py-3 border-b border-bg-border space-y-1">
          <div className="text-[10px] text-muted uppercase tracking-wider">Account</div>
          <div className="text-sm font-semibold text-white">
            ${tick.account.balance.toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-subtle">
            Equity ${tick.account.equity.toFixed(2)}
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? "bg-brand/20 text-brand border border-brand/30"
                  : "text-subtle hover:text-white hover:bg-white/5"
              }`
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Connection status */}
      <div className="px-4 py-3 border-t border-bg-border flex items-center gap-2 text-[11px]">
        {connected
          ? <><Wifi size={12} className="text-bull" /><span className="text-bull">Live</span></>
          : <><WifiOff size={12} className="text-bear" /><span className="text-bear">Offline</span></>
        }
        {tick?.bot_running && (
          <span className="ml-auto text-[10px] bg-bull/20 text-bull px-2 py-0.5 rounded-full border border-bull/30">
            BOT ON
          </span>
        )}
      </div>
    </aside>
  );
}
