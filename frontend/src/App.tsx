import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import PriceBar from "./components/PriceBar";
import AlertBanner from "./components/AlertBanner";
import Dashboard from "./pages/Dashboard";
import BotControl from "./pages/BotControl";
import Analysis from "./pages/Analysis";
import Trades from "./pages/Trades";
import History from "./pages/History";
import MarketAnalytics from "./pages/MarketAnalytics";
import { useNavigate } from "react-router-dom";

function AppInner() {
  const navigate = useNavigate();

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <PriceBar />
        {/* Setup alert banner — live WS feed, only renders when alerts exist */}
        <AlertBanner
          onAlertClick={() => navigate("/market-analytics")}
        />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/bot" element={<BotControl />} />
            <Route path="/market-analytics" element={<MarketAnalytics />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/trades" element={<Trades />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return <AppInner />;
}
