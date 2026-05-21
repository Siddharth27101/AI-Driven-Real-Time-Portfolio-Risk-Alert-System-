import { useEffect, useState, useRef } from "react";
import axios from "axios";

export default function Assistant() {
  const [query, setQuery]       = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const bottomRef = useRef(null);

  useEffect(() => {
    axios.get("http://127.0.0.1:8000/assistant/suggestions")
      .then(res => setSuggestions(res.data.suggestions || []));
    setMessages([{
      role: "ai",
      text: "👋 Hello! I am your AI Portfolio Risk Assistant powered by Amazon Bedrock.\n\nI can answer questions about all 100 client portfolios — risk levels, holdings, valuations, sector exposure, rebalancing needs, and more.\n\nTry one of the suggestions below or type your own question!",
      timestamp: new Date().toISOString()
    }]);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (q) => {
    const text = (q || query).trim();
    if (!text) return;
    setQuery("");
    setMessages(prev => [...prev, { role: "user", text, timestamp: new Date().toISOString() }]);
    setLoading(true);
    try {
      const res = await axios.post("http://127.0.0.1:8000/assistant/query", { query: text });
      setMessages(prev => [...prev, {
        role: "ai",
        text: res.data.answer,
        intent: res.data.intent,
        data: res.data.data,
        timestamp: res.data.timestamp
      }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "ai",
        text: "⚠️ Could not connect to backend. Make sure the backend is running on port 8000.",
        timestamp: new Date().toISOString()
      }]);
    }
    setLoading(false);
  };

  const formatText = (text) => {
    if (!text) return null;
    return text.split("\n").map((line, i) => {
      const bold = line.replace(/\*\*(.*?)\*\*/g, (_, m) => `<strong style="color:#f1f5f9">${m}</strong>`);
      return <div key={i} dangerouslySetInnerHTML={{ __html: bold || "&nbsp;" }}
                  style={{ lineHeight: "1.7", fontSize: "13px" }} />;
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 80px)" }}>
      <div className="page-title">AI Portfolio Assistant</div>
      <div className="page-sub">Ask anything about the 100 client portfolios · Powered by Amazon Bedrock</div>

      {/* Chat window */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column",
                    gap: "12px", padding: "4px 0 16px", marginBottom: "8px" }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            {msg.role === "ai" && (
              <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#1d4ed8",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: "16px", flexShrink: 0, marginRight: "10px", marginTop: "2px" }}>🤖</div>
            )}
            <div style={{
              maxWidth: "75%",
              background: msg.role === "user" ? "#1e3a5f" : "#0f172a",
              border: `1px solid ${msg.role === "user" ? "#2563eb" : "#1e293b"}`,
              borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              padding: "12px 16px", color: "#cbd5e1"
            }}>
              {formatText(msg.text)}
              <div style={{ fontSize: "10px", color: "#475569", marginTop: "6px" }}>
                {new Date(msg.timestamp).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"})}
                {msg.intent && msg.intent !== "help" && msg.intent !== "unknown" &&
                  <span style={{ marginLeft: "8px", background: "#1e293b", padding: "1px 6px",
                                 borderRadius: "4px", color: "#64748b" }}>intent: {msg.intent}</span>}
              </div>
            </div>
            {msg.role === "user" && (
              <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#334155",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: "16px", flexShrink: 0, marginLeft: "10px", marginTop: "2px" }}>👤</div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#1d4ed8",
                          display: "flex", alignItems: "center", justifyContent: "center", fontSize: "16px" }}>🤖</div>
            <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px",
                          padding: "12px 16px", color: "#64748b", fontSize: "13px" }}>
              Analyzing portfolios...
              <span style={{ display: "inline-block", animation: "pulse 1s infinite" }}> ●</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "11px", color: "#64748b", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Suggested questions
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {suggestions.slice(0, 8).map((s, i) => (
              <button key={i} onClick={() => send(s)} style={{
                background: "#111827", border: "1px solid #1e293b", borderRadius: "8px",
                padding: "6px 12px", color: "#94a3b8", fontSize: "12px", cursor: "pointer",
                transition: "all 0.15s"
              }}
                onMouseEnter={e => { e.target.style.borderColor = "#38bdf8"; e.target.style.color = "#e2e8f0"; }}
                onMouseLeave={e => { e.target.style.borderColor = "#1e293b"; e.target.style.color = "#94a3b8"; }}
              >{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div style={{ display: "flex", gap: "10px", alignItems: "center",
                    background: "#0f172a", border: "1px solid #1e293b",
                    borderRadius: "12px", padding: "10px 14px" }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Ask about portfolios, risk levels, holdings, prices..."
          style={{ flex: 1, background: "transparent", border: "none", outline: "none",
                   color: "#e2e8f0", fontSize: "14px" }}
        />
        <button onClick={() => send()} disabled={loading || !query.trim()} style={{
          background: query.trim() ? "#2563eb" : "#1e293b",
          border: "none", borderRadius: "8px", padding: "8px 16px",
          color: query.trim() ? "#fff" : "#475569", fontSize: "13px",
          fontWeight: 600, cursor: query.trim() ? "pointer" : "default",
          transition: "all 0.15s"
        }}>Send</button>
      </div>
    </div>
  );
}
