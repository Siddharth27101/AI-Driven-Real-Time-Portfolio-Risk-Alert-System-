import { useEffect, useState } from "react";
import axios from "axios";

export default function RiskAnalytics() {
  const [data, setData]     = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [tab, setTab]       = useState("HIGH");
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [prevSummary, setPrevSummary] = useState(null);

  const load = async () => {
    try {
      const [r, a] = await Promise.all([
        axios.get("http://127.0.0.1:8000/risk/analytics"),
        axios.get("http://127.0.0.1:8000/alerts?limit=30"),
      ]);
      setPrevSummary(data?.summary || null);
      setData(r.data);
      setAlerts(a.data.alerts || []);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // poll every 5 seconds so risk counts visibly change
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  if (loading) return <div className="spinner" />;

  const summary = data?.summary || {};
  const total   = summary.total || 0;

  // detect changes from last poll
  const changed = key => prevSummary && prevSummary[key] !== summary[key];

  const tabClients =
    tab === "HIGH"   ? data?.high_risk_clients   :
    tab === "MEDIUM" ? data?.medium_risk_clients  :
                       data?.low_risk_clients;

  return (
    <div>
      <div className="page-title">Risk Analytics</div>
      <div className="page-sub">
        <span className="live-dot" />
        Live — refreshes every 5s
        {lastUpdate && <span style={{color:"#475569",marginLeft:"8px"}}>· last updated {lastUpdate}</span>}
      </div>

      <div className="metric-grid">
        {[
          {key:"HIGH",  color:"#f87171", label:"High Risk"},
          {key:"MEDIUM",color:"#fbbf24", label:"Medium Risk"},
          {key:"LOW",   color:"#4ade80", label:"Low Risk"},
          {key:"total", color:"#e2e8f0", label:"Total Clients"},
        ].map(({key,color,label}) => (
          <div key={key} className="metric" style={{
            border: changed(key) ? "1px solid #38bdf8" : "1px solid #1e293b",
            transition:"border-color 0.5s"
          }}>
            <div className="metric-value" style={{color}}>
              {summary[key] ?? 0}
              {changed(key) && (
                <span style={{fontSize:"12px",marginLeft:"6px",color:"#38bdf8"}}>
                  {(summary[key]||0) > (prevSummary?.[key]||0) ? "▲" : "▼"}
                </span>
              )}
            </div>
            <div className="metric-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Risk distribution bar */}
      <div className="card">
        <div className="card-title">Live Risk Distribution</div>
        <div style={{display:"flex",height:"28px",borderRadius:"8px",overflow:"hidden",marginBottom:"10px"}}>
          <div style={{width:`${(summary.HIGH/total*100)||0}%`,background:"#7f1d1d",transition:"width 0.8s ease"}} />
          <div style={{width:`${(summary.MEDIUM/total*100)||0}%`,background:"#78350f",transition:"width 0.8s ease"}} />
          <div style={{width:`${(summary.LOW/total*100)||0}%`,background:"#14532d",transition:"width 0.8s ease"}} />
        </div>
        <div style={{display:"flex",gap:"16px",fontSize:"12px"}}>
          <span style={{color:"#f87171"}}>🔴 HIGH: {summary.HIGH} ({total?(summary.HIGH/total*100).toFixed(0):0}%)</span>
          <span style={{color:"#fbbf24"}}>🟡 MEDIUM: {summary.MEDIUM} ({total?(summary.MEDIUM/total*100).toFixed(0):0}%)</span>
          <span style={{color:"#4ade80"}}>🟢 LOW: {summary.LOW} ({total?(summary.LOW/total*100).toFixed(0):0}%)</span>
        </div>
        <div style={{fontSize:"11px",color:"#475569",marginTop:"8px"}}>
          ↑ Distribution changes every 5s as prices move and risk levels are recomputed dynamically
        </div>
      </div>

      <div className="card">
        <div className="card-title">Risk Detection Thresholds</div>
        <div className="feed">📊 <b>Allocation Drift &gt; 5%</b> → MEDIUM risk — holding has moved away from target weight</div>
        <div className="feed">📈 <b>Single Stock &gt; 20%</b> → HIGH risk — concentration limit breached</div>
        <div className="feed">📉 <b>Daily Drop &gt; 3%</b> → HIGH risk — portfolio declined too much today</div>
      </div>

      {/* Client list by tab */}
      <div className="card">
        <div style={{display:"flex",gap:"8px",marginBottom:"16px"}}>
          {["HIGH","MEDIUM","LOW"].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding:"6px 16px",borderRadius:"8px",border:"none",cursor:"pointer",
              fontSize:"13px",fontWeight:600,
              background: tab===t?(t==="HIGH"?"#7f1d1d":t==="MEDIUM"?"#78350f":"#14532d"):"#1e293b",
              color: tab===t?"#fff":"#94a3b8"
            }}>
              {t} ({summary[t]??0})
            </button>
          ))}
        </div>
        {(!tabClients || tabClients.length===0) && <div className="feed">No clients in this category right now.</div>}
        {tabClients?.map(c => (
          <div key={c.clientId} className="client" style={{cursor:"default"}}>
            <div>
              <div className="client-name">{c.clientId}</div>
              <div className="client-id">{c.risk_count} breach(es)</div>
            </div>
            <div style={{textAlign:"right"}}>
              <span className={`badge badge-${c.risk_level}`}>{c.risk_level}</span>
              <div style={{color:"#e2e8f0",fontWeight:600,fontSize:"13px",marginTop:"4px"}}>
                ${Number(c.portfolio_value).toLocaleString(undefined,{maximumFractionDigits:0})}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Alert table */}
      <div className="card">
        <div className="card-title">Recent Risk Alerts ({alerts.length})</div>
        {alerts.length===0
          ? <div className="feed">No alerts yet — price simulation running...</div>
          : (
            <table>
              <thead><tr>
                <th>Client</th><th>Risk Level</th><th>Portfolio Value</th><th>Time</th><th>Status</th>
              </tr></thead>
              <tbody>
                {alerts.map(a => (
                  <tr key={a.alert_id}>
                    <td style={{color:"#38bdf8",fontWeight:600}}>{a.client_id}</td>
                    <td><span className={`badge badge-${a.risk_level}`}>{a.risk_level}</span></td>
                    <td>${Number(a.portfolio_value).toLocaleString(undefined,{maximumFractionDigits:0})}</td>
                    <td style={{color:"#64748b",fontSize:"12px"}}>{new Date(a.timestamp).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"})}</td>
                    <td style={{color:"#4ade80",fontSize:"12px"}}>{a.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
