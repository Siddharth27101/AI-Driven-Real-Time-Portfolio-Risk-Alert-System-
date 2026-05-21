import { useEffect, useState } from "react";
import axios from "axios";

export default function AIFeed() {
  const [alerts, setAlerts]   = useState([]);
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    Promise.all([
      axios.get("http://127.0.0.1:8000/alerts?limit=20"),
      axios.get("http://127.0.0.1:8000/insights?limit=10"),
    ]).then(([a, i]) => {
      setAlerts(a.data.alerts || []);
      setInsights(i.data.insights || []);
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);

  if (loading) return <div className="spinner" />;

  return (
    <div>
      <div className="page-title">Real-Time AI Feed</div>
      <div className="page-sub">
        <span className="live-dot" />
        Live risk alerts and AI-generated insights · Auto-refreshes every 6 seconds
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"20px"}}>
        {/* Alerts */}
        <div className="card">
          <div className="card-title">⚠️ Risk Alerts ({alerts.length})</div>
          {alerts.length === 0 && <div className="feed">No alerts yet — price simulation running...</div>}
          {alerts.map(a => (
            <div key={a.alert_id} className="feed" style={{borderLeft:`3px solid ${a.risk_level==="HIGH"?"#f87171":a.risk_level==="MEDIUM"?"#fbbf24":"#4ade80"}`}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"4px"}}>
                <b style={{color:"#38bdf8"}}>{a.client_id}</b>
                <span className={`badge badge-${a.risk_level}`}>{a.risk_level}</span>
              </div>
              <div style={{fontSize:"12px",color:"#94a3b8"}}>
                Portfolio: ${Number(a.portfolio_value).toLocaleString(undefined,{maximumFractionDigits:0})}
              </div>
              <div style={{fontSize:"11px",color:"#475569",marginTop:"4px"}}>
                {new Date(a.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>

        {/* AI Insights */}
        <div className="card">
          <div className="card-title">🤖 AI Insights ({insights.length})</div>
          {insights.length === 0 && <div className="feed">AI insights will appear after risk alerts are generated.</div>}
          {insights.map(ins => (
            <div key={ins.insight_id} className="feed" style={{borderLeft:"3px solid #818cf8"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"6px"}}>
                <b style={{color:"#38bdf8"}}>{ins.client_id}</b>
                <span className={`badge badge-${ins.risk_level}`}>{ins.risk_level}</span>
              </div>
              <div style={{fontSize:"12px",color:"#cbd5e1",marginBottom:"4px"}}>{ins.explanation}</div>
              <div style={{fontSize:"12px",color:"#86efac",fontStyle:"italic"}}>{ins.suggested_action?.slice(0,100)}...</div>
              <div style={{fontSize:"11px",color:"#475569",marginTop:"4px"}}>
                {new Date(ins.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Event Stream Log</div>
        <div className="feed">✅ PriceUpdated events publishing every 5–10 seconds</div>
        <div className="feed">✅ Risk engine scanning portfolios on each price tick</div>
        <div className="feed">✅ RiskThresholdBreached events → AI Insight Service</div>
        <div className="feed">✅ AIInsightGenerated events saved to DynamoDB</div>
        <div className="feed">✅ EventBridge routing all events across microservices</div>
      </div>
    </div>
  );
}
