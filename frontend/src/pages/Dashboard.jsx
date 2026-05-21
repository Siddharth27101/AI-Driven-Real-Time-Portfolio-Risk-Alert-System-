import { useEffect, useState, useRef } from "react";
import axios from "axios";

export default function Dashboard() {
  const [stats, setStats]     = useState(null);
  const [prices, setPrices]   = useState({});
  const [prevPrices, setPrev] = useState({});
  const [flash, setFlash]     = useState({});
  const [loading, setLoading] = useState(true);
  const [tick, setTick]       = useState(0);
  const prevRef = useRef({});

  const load = async () => {
    try {
      const [s, p] = await Promise.all([
        axios.get("http://127.0.0.1:8000/dashboard/stats"),
        axios.get("http://127.0.0.1:8000/prices"),
      ]);
      const newPrices = p.data.prices || {};
      const newFlash  = {};

      // detect which prices changed and flash them
      Object.keys(newPrices).forEach(t => {
        const old = prevRef.current[t];
        if (old && old !== newPrices[t]) {
          newFlash[t] = newPrices[t] > old ? "up" : "down";
        }
      });

      setPrev({ ...prevRef.current });
      prevRef.current = newPrices;
      setPrices(newPrices);
      setFlash(newFlash);
      setStats(s.data);
      setTick(n => n + 1);

      // clear flash after 1.5s
      if (Object.keys(newFlash).length > 0) {
        setTimeout(() => setFlash({}), 1500);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // poll every 5 seconds — matches backend simulation interval
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const fmt = n => n != null ? Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";

  return (
    <div>
      <style>{`
        @keyframes flashUp   { 0%{background:#14532d} 100%{background:#111827} }
        @keyframes flashDown { 0%{background:#7f1d1d} 100%{background:#111827} }
        .flash-up   { animation: flashUp   1.5s ease-out; }
        .flash-down { animation: flashDown 1.5s ease-out; }
      `}</style>

      <div className="page-title">Enterprise AI Portfolio Dashboard</div>
      <div className="page-sub">
        <span className="live-dot" />
        Live — prices update every 5s · tick #{tick} · {new Date().toLocaleTimeString()}
      </div>

      {loading ? <div className="spinner" /> : (
        <>
          <div className="metric-grid">
            <div className="metric">
              <div className="metric-value">{stats?.total_clients ?? "—"}</div>
              <div className="metric-label">Total Clients</div>
            </div>
            <div className="metric">
              <div className="metric-value">${fmt(stats?.total_aum)}</div>
              <div className="metric-label">Total AUM</div>
            </div>
            <div className="metric">
              <div className="metric-value" style={{color:"#f87171"}}>{stats?.high_risk ?? "—"}</div>
              <div className="metric-label">High Risk</div>
            </div>
            <div className="metric">
              <div className="metric-value" style={{color:"#fbbf24"}}>{stats?.medium_risk ?? "—"}</div>
              <div className="metric-label">Medium Risk</div>
            </div>
            <div className="metric">
              <div className="metric-value" style={{color:"#4ade80"}}>{stats?.low_risk ?? "—"}</div>
              <div className="metric-label">Low Risk</div>
            </div>
            <div className="metric">
              <div className="metric-value">{stats?.total_alerts ?? "—"}</div>
              <div className="metric-label">Total Alerts</div>
            </div>
          </div>

          {/* Live price grid with flash animation */}
          <div className="card">
            <div className="card-title">
              📈 Live Market Prices
              <span style={{fontWeight:400,color:"#475569",marginLeft:"8px",fontSize:"11px"}}>
                — flashes green=up red=down
              </span>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(105px,1fr))",gap:"8px"}}>
              {Object.entries(prices).map(([ticker, price]) => {
                const prev   = prevRef.current[ticker];
                const chg    = prev ? ((price - prev) / prev * 100) : 0;
                const dir    = flash[ticker];
                const color  = dir === "up" ? "#4ade80" : dir === "down" ? "#f87171" : "#e2e8f0";
                return (
                  <div key={ticker}
                    className={dir === "up" ? "flash-up" : dir === "down" ? "flash-down" : ""}
                    style={{background:"#111827",border:`1px solid ${dir?"#334155":"#1e293b"}`,
                            borderRadius:"10px",padding:"10px 8px",textAlign:"center",transition:"border-color 0.3s"}}>
                    <div style={{color:"#38bdf8",fontWeight:700,fontSize:"12px"}}>{ticker}</div>
                    <div style={{color,fontWeight:600,fontSize:"15px",margin:"2px 0"}}>${Number(price).toFixed(2)}</div>
                    <div style={{fontSize:"10px",color: chg>=0?"#4ade80":"#f87171"}}>
                      {chg !== 0 ? `${chg >= 0 ? "▲" : "▼"} ${Math.abs(chg).toFixed(2)}%` : "—"}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-title">System Status</div>
            <div className="feed">✅ {stats?.total_clients ?? 0} Client Portfolios Loaded</div>
            <div className="feed">✅ {stats?.equities_tracked ?? 0} Equities Tracked — prices update every 5–10s</div>
            <div className="feed">✅ AI Risk Monitoring Active — alerts generated in real-time</div>
            <div className="feed">✅ Price simulation: normal ticks ±1.5%, news events ±6%</div>
            <div className="feed">✅ Amazon Bedrock AI insight generation active</div>
          </div>
        </>
      )}
    </div>
  );
}
