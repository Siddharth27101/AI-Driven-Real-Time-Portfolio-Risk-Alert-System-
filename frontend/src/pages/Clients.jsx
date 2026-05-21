import { useEffect, useState, useRef } from "react";
import axios from "axios";

const FEED_COLORS = {
  ALLOCATION_DRIFT:          { bg:"#1a1a2e", border:"#fbbf24", icon:"⚠️" },
  SINGLE_STOCK_OVEREXPOSURE: { bg:"#1a0a0a", border:"#f87171", icon:"🔴" },
  DAILY_DROP:                { bg:"#1a0a0a", border:"#f87171", icon:"📉" },
  PRICE_MOVE:                { bg:"#0a1a0a", border:"#4ade80", icon:"💹" },
};

export default function Clients() {
  const [clients, setClients]   = useState([]);
  const [selected, setSelected] = useState(null);
  const [insight, setInsight]   = useState(null);
  const [feed, setFeed]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");
  const feedRef = useRef(null);

  // Re-poll clients every 5s so risk badges and values update live
  useEffect(() => {
    const loadClients = () => {
      axios.get("http://127.0.0.1:8000/clients")
        .then(res => {
          setClients(res.data);
          if (!selected && res.data.length > 0) setSelected(res.data[0]);
          // update selected client data if still viewing one
          setSelected(prev => {
            if (!prev) return res.data[0] || null;
            const updated = res.data.find(c => c.clientId === prev.clientId);
            return updated || prev;
          });
        })
        .finally(() => setLoading(false));
    };
    loadClients();
    const t = setInterval(loadClients, 5000);
    return () => clearInterval(t);
  }, []);

  // When selected client changes — load insight + feed
  useEffect(() => {
    if (!selected) return;
    setInsight(null);
    setFeed([]);

    axios.get(`http://127.0.0.1:8000/insights/${selected.clientId}/latest`)
      .then(res => setInsight(res.data))
      .catch(() => setInsight(null));

    axios.get(`http://127.0.0.1:8000/feed/${selected.clientId}?limit=20`)
      .then(res => setFeed(res.data.feed || []))
      .catch(() => setFeed([]));
  }, [selected?.clientId]);

  // Poll feed every 6 seconds for selected client
  useEffect(() => {
    if (!selected) return;
    const t = setInterval(() => {
      axios.get(`http://127.0.0.1:8000/feed/${selected.clientId}?limit=20`)
        .then(res => setFeed(res.data.feed || []))
        .catch(() => {});
    }, 6000);
    return () => clearInterval(t);
  }, [selected?.clientId]);

  const filtered = clients.filter(c =>
    c.clientId.toLowerCase().includes(search.toLowerCase()) ||
    c.clientName.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="spinner" />;

  return (
    <div>
      <div className="page-title">Client Portfolios</div>
      <div className="page-sub">{clients.length} clients · Select a client to view holdings, AI insight &amp; live action feed</div>

      <div className="two-col">
        {/* ── Left: client list ── */}
        <div>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="🔍 Search by ID or name..."
            style={{width:"100%",background:"#111827",border:"1px solid #1e293b",borderRadius:"8px",
                    padding:"8px 12px",color:"#e2e8f0",fontSize:"13px",marginBottom:"8px",outline:"none"}}
          />
          <div className="scroll-list">
            {filtered.map(c => (
              <div key={c.clientId}
                className={"client" + (selected?.clientId === c.clientId ? " selected" : "")}
                onClick={() => setSelected(c)}
              >
                <div>
                  <div className="client-name">{c.clientId}</div>
                  <div className="client-id">{c.clientName} · {c.holdings?.length} holdings</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <span className={`badge badge-${c.risk}`}>{c.risk}</span>
                  <div style={{fontSize:"11px",color:"#64748b",marginTop:"4px"}}>
                    ${Number(c.value).toLocaleString(undefined,{maximumFractionDigits:0})}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: detail panel ── */}
        {selected && (
          <div style={{display:"flex",flexDirection:"column",gap:"16px"}}>

            {/* Portfolio summary */}
            <div className="card">
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:"14px"}}>
                <div>
                  <div style={{fontSize:"18px",fontWeight:700,color:"#f1f5f9"}}>{selected.clientId}</div>
                  <div style={{fontSize:"13px",color:"#64748b"}}>{selected.clientName}</div>
                </div>
                <span className={`badge badge-${selected.risk}`}>{selected.risk} RISK</span>
              </div>

              <div className="metric-grid" style={{gridTemplateColumns:"repeat(3,1fr)"}}>
                <div className="metric">
                  <div className="metric-value">${Number(selected.value).toLocaleString(undefined,{maximumFractionDigits:0})}</div>
                  <div className="metric-label">Portfolio Value</div>
                </div>
                <div className="metric">
                  <div className="metric-value">{selected.exposure}%</div>
                  <div className="metric-label">Max Exposure</div>
                </div>
                <div className="metric">
                  <div className="metric-value">{selected.riskCount}</div>
                  <div className="metric-label">Risk Breaches</div>
                </div>
              </div>

              {/* Holdings table */}
              <div className="card-title" style={{marginTop:"16px"}}>Holdings</div>
              <div style={{display:"grid",gridTemplateColumns:"55px 70px 75px 85px 60px 70px 60px",
                           fontSize:"11px",color:"#64748b",padding:"0 4px 6px",gap:"0"}}>
                <span>TICKER</span><span>SECTOR</span><span>SHARES</span>
                <span>PRICE</span><span>VALUE</span><span>ALLOC%</span><span>DRIFT</span>
              </div>
              {selected.holdings?.map((h, i) => (
                <div key={i} className="holding">
                  <span className="holding-ticker">{h.symbol}</span>
                  <span style={{fontSize:"11px",color:"#64748b",width:"70px"}}>{h.sector}</span>
                  <span className="holding-shares">{Number(h.shares).toFixed(1)}</span>
                  <span className="holding-price">${Number(h.price).toFixed(2)}</span>
                  <span className="holding-value">${Number(h.value).toLocaleString(undefined,{maximumFractionDigits:0})}</span>
                  <span style={{color:"#94a3b8",fontSize:"12px",width:"60px"}}>{h.allocation_pct?.toFixed(1)}%</span>
                  <span style={{color: h.drift_pct > 5 ? "#f87171" : h.drift_pct < -5 ? "#fbbf24" : "#4ade80",
                                fontSize:"12px",fontWeight:600}}>
                    {h.drift_pct > 0 ? "+" : ""}{h.drift_pct?.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>

            {/* Real-time Action Feed */}
            <div className="card">
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"12px"}}>
                <div className="card-title" style={{margin:0}}>📡 Real-Time Action Feed</div>
                <div style={{display:"flex",alignItems:"center",gap:"6px",fontSize:"12px",color:"#64748b"}}>
                  <span className="live-dot" />
                  Live · {feed.length} events
                </div>
              </div>

              {feed.length === 0 ? (
                <div className="feed" style={{color:"#475569",fontStyle:"italic"}}>
                  Waiting for events — price simulation runs every 5–10 seconds...
                </div>
              ) : (
                <div ref={feedRef} style={{maxHeight:"220px",overflowY:"auto"}}>
                  {feed.map(entry => {
                    const style = FEED_COLORS[entry.type] || {bg:"#111827",border:"#334155",icon:"🔔"};
                    return (
                      <div key={entry.id} style={{
                        background: style.bg,
                        border: `1px solid ${style.border}`,
                        borderLeft: `3px solid ${style.border}`,
                        borderRadius:"8px", padding:"8px 12px",
                        marginBottom:"6px", display:"flex",
                        alignItems:"flex-start", gap:"8px"
                      }}>
                        <span style={{fontSize:"14px",marginTop:"1px"}}>{style.icon}</span>
                        <div style={{flex:1}}>
                          <div style={{fontSize:"13px",color:"#e2e8f0",lineHeight:"1.4"}}>{entry.message}</div>
                          <div style={{fontSize:"11px",color:"#475569",marginTop:"3px"}}>
                            {new Date(entry.timestamp).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"})} · {entry.type.replace(/_/g," ")}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* AI Insight */}
            <div className="card">
              <div className="card-title">🤖 AI Risk Insight (Amazon Bedrock)</div>
              {insight ? (
                <>
                  <div className="insight-box insight-explanation">
                    <div className="insight-label">What's happening</div>
                    {insight.explanation}
                  </div>
                  <div className="insight-box insight-action">
                    <div className="insight-label">Suggested Action</div>
                    {insight.suggested_action}
                  </div>
                  {insight.severity_reasoning && (
                    <div className="feed" style={{marginTop:"10px"}}>
                      <b>Severity reasoning:</b> {insight.severity_reasoning}
                    </div>
                  )}
                  <div className="insight-box insight-disclaimer">{insight.disclaimer}</div>
                </>
              ) : (
                <div className="feed" style={{color:"#475569",fontStyle:"italic"}}>
                  AI insight will appear once a risk threshold is breached for this client.
                </div>
              )}
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
