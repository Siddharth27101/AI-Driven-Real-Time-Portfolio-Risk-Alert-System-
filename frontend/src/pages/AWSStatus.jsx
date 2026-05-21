export default function AWSStatus() {
  const services = [
    { name:"Amazon API Gateway",   icon:"🌐", status:"Active",    desc:"REST API entry point — routes requests to microservices" },
    { name:"AWS Lambda",           icon:"⚡", status:"Active",    desc:"Serverless compute for all 4 microservices" },
    { name:"Amazon DynamoDB",      icon:"🗄️",  status:"Active",    desc:"3 tables: portfolios, risk-alerts, ai-insights" },
    { name:"Amazon EventBridge",   icon:"📡", status:"Active",    desc:"Event bus routing PriceUpdated, RiskThresholdBreached, AIInsightGenerated" },
    { name:"Amazon SQS",           icon:"📬", status:"Active",    desc:"4 queues: price-updates-q, risk-alerts-q, ai-insights-q, portfolio-events-q" },
    { name:"Amazon CloudWatch",    icon:"📊", status:"Active",    desc:"Logs and alarms for all Lambda functions" },
    { name:"Amazon Bedrock",       icon:"🤖", status:"Mock (Dev)","desc":"Claude model for AI insights — mock active for local dev, real on AWS" },
    { name:"AWS CDK",              icon:"🏗️",  status:"Ready",     desc:"Infrastructure as Code — run cdk deploy to provision all resources" },
  ];

  const microservices = [
    { name:"Portfolio Service",    port:"8001", desc:"Stores 100 client portfolios, exposes REST APIs, computes allocation breakdown" },
    { name:"Market Data Service",  port:"8002", desc:"Simulates price streaming for 20 equities, publishes PriceUpdated events every 5–10s" },
    { name:"Risk Service",         port:"8003", desc:"Detects drift >5%, concentration >20%, daily drop >3%, publishes risk alerts" },
    { name:"AI Insight Service",   port:"8004", desc:"Consumes risk events, calls Amazon Bedrock, generates structured JSON insights" },
  ];

  return (
    <div>
      <div className="page-title">AWS Services Status</div>
      <div className="page-sub">Infrastructure overview — all services mocked locally via moto</div>

      <div className="card">
        <div className="card-title">AWS Services</div>
        {services.map(s => (
          <div key={s.name} className="feed" style={{display:"flex",alignItems:"flex-start",gap:"12px"}}>
            <span style={{fontSize:"20px"}}>{s.icon}</span>
            <div style={{flex:1}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <b style={{color:"#e2e8f0"}}>{s.name}</b>
                <span style={{
                  fontSize:"11px",fontWeight:600,padding:"2px 8px",borderRadius:"999px",
                  background: s.status==="Active"?"#14532d":s.status==="Mock (Dev)"?"#78350f":"#1e3a5f",
                  color: s.status==="Active"?"#4ade80":s.status==="Mock (Dev)"?"#fbbf24":"#38bdf8"
                }}>{s.status}</span>
              </div>
              <div style={{fontSize:"12px",color:"#64748b",marginTop:"2px"}}>{s.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Microservices</div>
        {microservices.map(m => (
          <div key={m.name} className="feed">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"4px"}}>
              <b style={{color:"#38bdf8"}}>{m.name}</b>
              <span style={{fontSize:"11px",color:"#4ade80",background:"#14532d",padding:"2px 8px",borderRadius:"999px"}}>
                :{m.port}
              </span>
            </div>
            <div style={{fontSize:"12px",color:"#64748b"}}>{m.desc}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Event Flow</div>
        <div className="feed">1. Market Data Service → publishes <b>PriceUpdated</b> → EventBridge → SQS price-updates-q</div>
        <div className="feed">2. Risk Service → consumes price events → detects breaches → publishes <b>RiskThresholdBreached</b></div>
        <div className="feed">3. AI Insight Service → consumes risk events → calls Bedrock → publishes <b>AIInsightGenerated</b></div>
        <div className="feed">4. Dashboard → polls REST APIs → displays alerts + AI commentary in real-time</div>
      </div>

      <div className="card">
        <div className="card-title">Deploy to Real AWS</div>
        <div className="feed" style={{fontFamily:"monospace",fontSize:"12px"}}>
          cd infrastructure/cdk<br/>
          pip install aws-cdk-lib constructs<br/>
          cdk bootstrap<br/>
          cdk deploy<br/>
          curl -X POST https://&lt;api-url&gt;/prod/admin/seed
        </div>
      </div>
    </div>
  );
}
