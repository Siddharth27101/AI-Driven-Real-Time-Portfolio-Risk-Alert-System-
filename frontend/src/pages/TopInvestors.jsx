import { useEffect, useState } from "react";
import axios from "axios";

const MEDALS = ["🥇","🥈","🥉","4️⃣","5️⃣"];

export default function TopInvestors() {
  const [investors, setInvestors] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get("http://127.0.0.1:8000/top-investors")
      .then(res => setInvestors(res.data.top_investors || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="spinner" />;

  return (
    <div>
      <div className="page-title">Top 5 Investors</div>
      <div className="page-sub">Ranked by total portfolio value</div>

      {investors.map((inv, i) => (
        <div key={inv.clientId} className="card" style={{display:"flex",alignItems:"center",gap:"20px"}}>
          <div style={{fontSize:"36px"}}>{MEDALS[i]}</div>
          <div style={{flex:1}}>
            <div style={{fontSize:"18px",fontWeight:700,color:"#f1f5f9"}}>{inv.clientId}</div>
            <div style={{fontSize:"13px",color:"#64748b"}}>{inv.clientName}</div>
          </div>
          <div style={{textAlign:"right"}}>
            <div style={{fontSize:"24px",fontWeight:700,color:"#4ade80"}}>
              ${Number(inv.portfolio_value).toLocaleString(undefined,{maximumFractionDigits:0})}
            </div>
            <div style={{fontSize:"12px",color:"#64748b"}}>Total Portfolio Value</div>
          </div>
        </div>
      ))}

      <div className="card">
        <div className="card-title">About Portfolio Ranking</div>
        <div className="feed">Rankings are computed in real-time based on current market prices across all 20 equities.</div>
        <div className="feed">Values update automatically every 5–10 seconds as prices change.</div>
      </div>
    </div>
  );
}
