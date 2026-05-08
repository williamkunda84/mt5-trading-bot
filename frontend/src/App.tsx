import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import PriceBar from "./components/PriceBar";
import Dashboard from "./pages/Dashboard";
import BotControl from "./pages/BotControl";
import Analysis from "./pages/Analysis";
import Trades from "./pages/Trades";
import History from "./pages/History";

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <PriceBar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/bot" element={<BotControl />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/trades" element={<Trades />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
