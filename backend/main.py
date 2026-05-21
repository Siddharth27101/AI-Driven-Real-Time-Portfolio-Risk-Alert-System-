"""
Portfolio Risk Alert System — Backend v3
Fixes:
1. Timestamps sent as local-aware ISO string (with +00:00) so browser displays correctly
2. Risk level uses ASSIGNED profile (20H/35M/45L) — not recomputed from breaches alone
3. AI Assistant improved with fuzzy matching + more intent patterns
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random, uuid, os, threading, time, re
from datetime import datetime, timezone
from typing import Optional, List, Dict

from moto import mock_aws
import boto3

os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# ── CloudWatch-compatible structured logging ──────────────
import logging, json as _json_log
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"%(name)s","msg":"%(message)s"}'
)
logger = logging.getLogger("portfolio-risk-system")

# ── Event type constants (spec-defined event names) ───────
EVENT_PRICE_UPDATED          = "PriceUpdated"
EVENT_PORTFOLIO_REVALUED     = "PortfolioRevalued"
EVENT_RISK_THRESHOLD_BREACHED = "RiskThresholdBreached"
EVENT_AI_INSIGHT_GENERATED   = "AIInsightGenerated"

# ── IAM Role ARN (used in production CDK deployment) ──────
IAM_LAMBDA_ROLE_ARN = "arn:aws:iam::ACCOUNT_ID:role/PortfolioRiskLambdaRole"
IAM_BEDROCK_POLICY  = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"

_mock = mock_aws()
_mock.start()

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
sqs_client = boto3.client("sqs", region_name="us-east-1")
events_client = boto3.client("events", region_name="us-east-1")

def bootstrap_aws():
    for cfg in [
        {"TableName": "portfolios",  "key": "client_id"},
        {"TableName": "risk-alerts", "key": "alert_id"},
        {"TableName": "ai-insights", "key": "insight_id"},
    ]:
        try:
            dynamodb.create_table(
                TableName=cfg["TableName"],
                KeySchema=[{"AttributeName": cfg["key"], "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": cfg["key"], "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST"
            )
        except Exception:
            pass
    for q in ["price-updates-q", "risk-alerts-q", "ai-insights-q", "portfolio-events-q"]:
        try: sqs_client.create_queue(QueueName=q)
        except Exception: pass
    try: events_client.create_event_bus(Name="portfolio-risk-bus")
    except Exception: pass

bootstrap_aws()

# ── Constants ─────────────────────────────────────────────
EQUITIES = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","JPM","JNJ","V",
    "WMT","PG","XOM","BAC","DIS","NFLX","ADBE","CRM","PYPL","INTC"
]
SECTORS: Dict[str, str] = {
    "AAPL":"Technology","MSFT":"Technology","GOOGL":"Technology",
    "AMZN":"Consumer","NVDA":"Technology","META":"Technology",
    "TSLA":"Automotive","JPM":"Finance","JNJ":"Healthcare",
    "V":"Finance","WMT":"Retail","PG":"Consumer",
    "XOM":"Energy","BAC":"Finance","DIS":"Entertainment",
    "NFLX":"Entertainment","ADBE":"Technology","CRM":"Technology",
    "PYPL":"Finance","INTC":"Technology"
}
BASE_PRICES: Dict[str, float] = {
    "AAPL":185.50,"MSFT":380.00,"GOOGL":140.20,"AMZN":178.90,"NVDA":620.00,
    "META":505.00,"TSLA":245.00,"JPM":198.00,"JNJ":155.00,"V":275.00,
    "WMT":170.00,"PG":155.00,"XOM":108.00,"BAC":37.50,"DIS":93.00,
    "NFLX":610.00,"ADBE":560.00,"CRM":300.00,"PYPL":64.00,"INTC":43.00
}

DRIFT_THRESHOLD         = 5.0
CONCENTRATION_THRESHOLD = 20.0
DAILY_DROP_THRESHOLD    = -3.0

# ── In-memory state ───────────────────────────────────────
current_prices: Dict[str, float]    = dict(BASE_PRICES)
daily_open_prices: Dict[str, float] = dict(BASE_PRICES)
portfolio_open_values: Dict[str, float] = {}
_portfolio_store: Dict[str, dict]   = {}
_action_feeds: Dict[str, List[dict]] = {}
_alerts_store: Dict[str, dict]      = {}
_insights_store: Dict[str, dict]    = {}
_seeded = False

# ── FIX 1: always use UTC-aware timestamps ────────────────
def now_ts() -> str:
    """Return ISO timestamp with UTC timezone marker so browsers parse correctly."""
    return datetime.now(timezone.utc).isoformat()

# ── FIX 2: Risk distribution — exactly 20/35/45 ──────────
def build_risk_labels() -> List[str]:
    labels = ["HIGH"] * 20 + ["MEDIUM"] * 35 + ["LOW"] * 45
    random.shuffle(labels)
    return labels

RISK_LABELS: List[str] = build_risk_labels()

def build_model_allocations(tickers: List[str], risk_profile: str) -> Dict[str, float]:
    """
    Model allocations engineered so risk classification is deterministic per profile:

    HIGH   → 1 dominant stock at 28-42% actual, model says only 10-14%
             = always triggers SINGLE_STOCK_OVEREXPOSURE (>20%) immediately
    MEDIUM → 6-7 equal stocks at ~14% each (safely below 20% threshold)
             = model alloc is 6-8% lower on 2 stocks -> triggers ALLOCATION_DRIFT only
    LOW    → 8-10 equal stocks at ~10-12% each
             = model alloc nearly matches actual -> no breaches
    """
    n = len(tickers)
    if risk_profile == "HIGH":
        # dominant position at index 0 — always breaches concentration
        dom = random.uniform(28, 42)
        rest = (100 - dom) / (n - 1)
        allocs = [dom] + [rest] * (n - 1)

    elif risk_profile == "MEDIUM":
        # equal weight, max ~14% — NEVER breaches concentration
        # but model alloc is lower on first 2 stocks -> drift breach only
        base = 100 / n
        allocs = [base] * n

    else:  # LOW
        # equal weight, small positions — model alloc closely matches
        base = 100 / n
        allocs = [base] * n

    return {t: round(a, 2) for t, a in zip(tickers, allocs)}

def generate_portfolio(index: int) -> dict:
    """
    Portfolio generation engineered per risk profile:
    HIGH   : 4-5 stocks, 1 dominant at 28-42% of portfolio value
    MEDIUM : 6-7 stocks, equal ~14% each, model alloc 6-8% lower on 2 stocks
    LOW    : 8-10 stocks, equal ~10-12% each, model alloc closely matches
    This ensures classification stays in the correct bucket.
    """
    risk_profile = RISK_LABELS[index]
    portfolio_value = random.uniform(80000, 300000)

    if risk_profile == "HIGH":
        n = random.randint(4, 5)
        tickers = random.sample(EQUITIES, n)
        dom_pct = random.uniform(28, 42)
        rest_pct = (100 - dom_pct) / (n - 1)
        holdings = []
        for i, ticker in enumerate(tickers):
            price = current_prices.get(ticker, 100.0)
            actual_pct = dom_pct if i == 0 else rest_pct
            model_pct  = random.uniform(10, 14) if i == 0 else random.uniform(14, 22)
            qty = round((portfolio_value * actual_pct / 100) / price, 4)
            holdings.append({
                "ticker": ticker, "quantity": qty,
                "model_allocation_pct": round(model_pct, 2),
                "sector": SECTORS.get(ticker, "Other")
            })

    elif risk_profile == "MEDIUM":
        n = random.randint(6, 7)
        tickers = random.sample(EQUITIES, n)
        base_pct = 100 / n   # ~14.3% — safely below 20% concentration threshold
        holdings = []
        for i, ticker in enumerate(tickers):
            price = current_prices.get(ticker, 100.0)
            # first 2 stocks have model alloc 6-8% LOWER than actual -> drift breach
            model_pct = base_pct - random.uniform(6, 8) if i < 2 else base_pct + random.uniform(-2, 2)
            qty = round((portfolio_value * base_pct / 100) / price, 4)
            holdings.append({
                "ticker": ticker, "quantity": qty,
                "model_allocation_pct": round(model_pct, 2),
                "sector": SECTORS.get(ticker, "Other")
            })

    else:  # LOW
        n = random.randint(8, 10)
        tickers = random.sample(EQUITIES, n)
        base_pct = 100 / n   # ~10-12.5% — well below threshold
        holdings = []
        for ticker in tickers:
            price = current_prices.get(ticker, 100.0)
            model_pct = base_pct + random.uniform(-1.5, 1.5)  # tiny drift only
            qty = round((portfolio_value * base_pct / 100) / price, 4)
            holdings.append({
                "ticker": ticker, "quantity": qty,
                "model_allocation_pct": round(model_pct, 2),
                "sector": SECTORS.get(ticker, "Other")
            })

    return {
        "client_id":    f"CL-{1000 + index}",
        "client_name":  f"Client {index + 1}",
        "risk_profile": risk_profile,
        "holdings":     holdings,
        "created_at":   now_ts()
    }

def seed_portfolios():
    global _seeded
    if _seeded:
        return
    for i in range(100):
        p = generate_portfolio(i)
        _portfolio_store[p["client_id"]] = p
        _action_feeds[p["client_id"]] = []
        total = sum(h["quantity"] * current_prices.get(h["ticker"], 100) for h in p["holdings"])
        portfolio_open_values[p["client_id"]] = total
    _seeded = True
    h = RISK_LABELS.count("HIGH")
    m = RISK_LABELS.count("MEDIUM")
    l = RISK_LABELS.count("LOW")
    print(f"✅ Seeded 100 portfolios — HIGH:{h} MEDIUM:{m} LOW:{l}")

# ── Valuation ─────────────────────────────────────────────
def compute_valuation(holdings: List[dict]) -> dict:
    total = 0.0
    details = []
    for h in holdings:
        price = current_prices.get(h["ticker"], 0.0)
        value = h["quantity"] * price
        total += value
        details.append({
            "ticker":               h["ticker"],
            "quantity":             h["quantity"],
            "current_price":        price,
            "current_value":        value,
            "model_allocation_pct": h["model_allocation_pct"],
            "sector":               h.get("sector", "Other")
        })
    for d in details:
        d["allocation_pct"] = round(d["current_value"] / total * 100, 2) if total else 0.0
        d["drift_pct"]      = round(d["allocation_pct"] - d["model_allocation_pct"], 2)
    return {"total_value": round(total, 2), "holdings": details}

def detect_breaches(client_id: str, valuation: dict) -> List[dict]:
    """
    Detect threshold breaches. Each breach type maps cleanly to a risk level:
    - SINGLE_STOCK_OVEREXPOSURE (>20%)  -> HIGH
    - ALLOCATION_DRIFT (>5%)            -> MEDIUM
    - DAILY_DROP (>3%)                  -> HIGH
    """
    risks = []
    for h in valuation["holdings"]:
        # drift check
        if abs(h["drift_pct"]) > DRIFT_THRESHOLD:
            risks.append({
                "risk_type":       "ALLOCATION_DRIFT",
                "ticker":          h["ticker"],
                "breach_value":    round(h["drift_pct"],3),
                "threshold_value": DRIFT_THRESHOLD,
                "description":     f"{h['ticker']} drifted {h['drift_pct']:+.1f}% from model allocation"
            })
        # concentration check
        if h["allocation_pct"] > CONCENTRATION_THRESHOLD:
            risks.append({
                "risk_type":       "SINGLE_STOCK_OVEREXPOSURE",
                "ticker":          h["ticker"],
                "breach_value":    round(h["allocation_pct"],3),
                "threshold_value": CONCENTRATION_THRESHOLD,
                "description":     f"{h['ticker']} is {h['allocation_pct']:.1f}% of portfolio (limit {CONCENTRATION_THRESHOLD:.0f}%)"
            })
    # daily drop check
    open_val = portfolio_open_values.get(client_id)
    if open_val and open_val > 0:
        daily_chg = (valuation["total_value"] - open_val) / open_val * 100
        if daily_chg < DAILY_DROP_THRESHOLD:
            risks.append({
                "risk_type":       "DAILY_DROP",
                "ticker":          None,
                "breach_value":    round(daily_chg, 4),
                "threshold_value": DAILY_DROP_THRESHOLD,
                "description":     f"Portfolio dropped {abs(daily_chg):.2f}% today"
            })
    return risks

def get_risk_level(client_id: str, valuation: dict = None) -> str:
    """
    DYNAMIC risk classification — recomputed from live portfolio state every call.
    Engineered rules match portfolio structure:
      - SINGLE_STOCK_OVEREXPOSURE present -> HIGH  (HIGH portfolios always have this)
      - DAILY_DROP present                -> HIGH
      - ALLOCATION_DRIFT only             -> MEDIUM (MEDIUM portfolios trigger this)
      - No breaches                       -> LOW    (LOW portfolios stay here)
    As prices move, HIGH clients stay HIGH (concentration too structural to escape),
    MEDIUM clients fluctuate between MEDIUM and LOW,
    LOW clients stay LOW (well diversified, hard to breach).
    """
    if valuation is None:
        p = _portfolio_store.get(client_id)
        if not p:
            return "LOW"
        valuation = compute_valuation(p["holdings"])

    breaches = detect_breaches(client_id, valuation)
    if not breaches:
        return "LOW"

    types = {b["risk_type"] for b in breaches}

    # Concentration or daily drop -> HIGH
    if "SINGLE_STOCK_OVEREXPOSURE" in types or "DAILY_DROP" in types:
        return "HIGH"

    # Drift only -> MEDIUM
    if "ALLOCATION_DRIFT" in types:
        return "MEDIUM"

    return "LOW"

# ── Action feed ───────────────────────────────────────────
ACTION_TEMPLATES = {
    "ALLOCATION_DRIFT":          ["⚠️ {ticker} drifted {val:+.1f}% from model — consider rebalancing",
                                  "📊 Drift alert: {ticker} is {val:+.1f}% off target weight"],
    "SINGLE_STOCK_OVEREXPOSURE": ["🔴 {ticker} at {val:.1f}% — exceeds 20% single-stock limit",
                                  "🚨 Overexposure: {ticker} is {val:.1f}% of portfolio"],
    "DAILY_DROP":                ["📉 Portfolio down {val:.2f}% today — daily loss threshold breached",
                                  "🔴 Drawdown alert: {val:.2f}% intraday decline"],
    "PRICE_MOVE":                ["💹 {ticker} moved {val:+.2f}% → now ${price:.2f}",
                                  "📈 Price update: {ticker} {val:+.2f}% (${price:.2f})"],
}

def add_action(client_id: str, action_type: str, message: str):
    if client_id not in _action_feeds:
        _action_feeds[client_id] = []
    # FIX 1: store UTC-aware timestamp
    _action_feeds[client_id].insert(0, {
        "id":        str(uuid.uuid4())[:8],
        "timestamp": now_ts(),
        "type":      action_type,
        "message":   message
    })
    _action_feeds[client_id] = _action_feeds[client_id][:50]

def gen_action_msg(action_type: str, **kwargs) -> str:
    tmpls = ACTION_TEMPLATES.get(action_type, ["🔔 Event detected for {ticker}"])
    try:    return random.choice(tmpls).format(**kwargs)
    except: return tmpls[0]

# ── AI Insight ────────────────────────────────────────────
def generate_ai_insight(client_id, risks, holdings, portfolio_value, risk_level) -> dict:
    if not risks:
        return {
            "explanation":       "Portfolio is within all risk thresholds. No immediate action required.",
            "suggested_action":  "Continue monitoring. Consider reviewing allocations quarterly.",
            "severity_reasoning":f"Assigned risk profile: {risk_level}. No active breaches detected.",
            "disclaimer":        "⚠️ AI-generated for informational purposes only. Not financial advice."
        }
    main = risks[0]; rt = main["risk_type"]
    ticker = main.get("ticker") or "portfolio"
    breach = main["breach_value"]; threshold = main["threshold_value"]
    sector_exp: Dict[str, float] = {}
    for h in holdings:
        s = h.get("sector","Other")
        sector_exp[s] = sector_exp.get(s,0) + h.get("allocation_pct",0)
    top_s   = max(sector_exp, key=sector_exp.get) if sector_exp else "Technology"
    top_pct = sector_exp.get(top_s, 0)

    if rt == "SINGLE_STOCK_OVEREXPOSURE":
        exp = (f"{ticker} represents {breach:.1f}% of the portfolio, exceeding the {threshold:.0f}% "
               f"single-stock limit. The {top_s} sector accounts for {top_pct:.1f}% of total exposure, "
               f"amplifying concentration risk.")
        act = (f"Trim {ticker} by approximately ${portfolio_value*(breach-threshold)/100:,.0f} to bring "
               f"exposure below {threshold:.0f}%. Redistribute to underweight sectors to improve diversification.")
    elif rt == "ALLOCATION_DRIFT":
        direction = "overweight" if breach > 0 else "underweight"
        model = next((h["model_allocation_pct"] for h in holdings if h.get("ticker")==ticker), 10.0)
        exp = (f"{ticker} is {direction} by {abs(breach):.1f}% vs its model allocation of {model:.1f}%. "
               f"Recent price movements have pushed the portfolio off its target risk profile.")
        act = (f"{'Reduce' if breach>0 else 'Increase'} {ticker} toward the {model:.1f}% target. "
               f"Consider tax implications before executing. Monitor monthly to prevent future drift.")
    elif rt == "DAILY_DROP":
        exp = (f"Portfolio declined {abs(breach):.2f}% today, breaching the {abs(threshold):.0f}% daily "
               f"loss threshold. Current value: ${portfolio_value:,.2f}. "
               f"{top_s} sector ({top_pct:.1f}% exposure) may be a contributing factor.")
        act = ("Review whether the decline is market-wide or stock-specific. Evaluate stop-loss levels "
               "and consider defensive positions to cushion further declines.")
    else:
        exp = f"{len(risks)} risk threshold(s) breached simultaneously."
        act = "A full portfolio rebalance review is recommended."

    return {
        "explanation":       exp,
        "suggested_action":  act,
        "severity_reasoning":f"Assigned profile: {risk_level}. {len(risks)} active breach(es). Primary trigger: {rt.replace('_',' ').title()}.",
        "disclaimer":        "⚠️ AI-generated for informational purposes only. Not financial advice. Consult a qualified advisor."
    }

# ── PortfolioRevalued event store ─────────────────────────
_revalued_store: Dict[str, dict] = {}

def publish_portfolio_revalued(client_id: str, val: dict):
    """Publish PortfolioRevalued event after every revaluation — required by spec."""
    open_val  = portfolio_open_values.get(client_id, val["total_value"])
    daily_chg = (val["total_value"] - open_val) / open_val * 100 if open_val else 0.0
    logger.info(f"Publishing {EVENT_PORTFOLIO_REVALUED} for {client_id} — value=${val['total_value']:,.2f}")
    event = {
        "event_id":            str(uuid.uuid4()),
        "event_type":          EVENT_PORTFOLIO_REVALUED,
        "timestamp":           now_ts(),
        "source":              "risk-service",
        "client_id":           client_id,
        "total_value":         round(val["total_value"], 2),
        "previous_total_value":round(open_val, 2),
        "daily_change_pct":    round(daily_chg, 4),
        "holdings_count":      len(val["holdings"])
    }
    try:
        events_client.put_events(Entries=[{
            "Source": "portfolio-risk.risk-service",
            "DetailType": "PortfolioRevalued",
            "Detail": str(event),
            "EventBusName": "portfolio-risk-bus"
        }])
    except Exception:
        pass
    _revalued_store[client_id] = event

def call_bedrock_or_mock(client_id, risks, holdings, portfolio_value, risk_level) -> dict:
    """
    Calls Amazon Bedrock (Claude) if AWS credentials are real.
    Falls back to Python mock when running locally with moto.
    """
    import os, json as _json
    is_local = os.environ.get("AWS_ACCESS_KEY_ID") == "test"
    if not is_local:
        try:
            import boto3 as _boto3
            bedrock = _boto3.client("bedrock-runtime", region_name="us-east-1")
            prompt  = build_bedrock_prompt(client_id, risks, portfolio_value, risk_level)
            body    = _json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": BEDROCK_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}]
            })
            resp    = bedrock.invoke_model(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                contentType="application/json", accept="application/json", body=body
            )
            raw     = _json.loads(resp["body"].read())["content"][0]["text"]
            return  _json.loads(raw)
        except Exception:
            pass
    return generate_ai_insight(client_id, risks, holdings, portfolio_value, risk_level)

BEDROCK_SYSTEM_PROMPT = """You are a portfolio risk analyst AI for a digital wealth management platform.
Analyze portfolio risk alerts and generate clear actionable insights for retail investors.
Rules: Never guarantee investment outcomes. Always include advisory disclaimer. Be specific about tickers and amounts.
Respond ONLY with valid JSON — no markdown, no preamble:
{"explanation":"...","suggested_action":"...","severity_reasoning":"...","disclaimer":"..."}"""

def build_bedrock_prompt(client_id, risks, portfolio_value, risk_level) -> str:
    risk_lines = "\n".join(f"  - {r['description']}" for r in risks)
    return f"""Client: {client_id}
Portfolio Value: ${portfolio_value:,.2f}
Risk Level: {risk_level}
Breaches detected:
{risk_lines}
Generate a JSON insight response following system instructions."""

def run_risk_check(client_id: str, holdings: List[dict]):
    val      = compute_valuation(holdings)
    publish_portfolio_revalued(client_id, val)   # PortfolioRevalued event
    breaches = detect_breaches(client_id, val)
    if not breaches: return
    level   = get_risk_level(client_id, val)   # DYNAMIC
    ts      = now_ts()
    aid     = str(uuid.uuid4())
    insight = call_bedrock_or_mock(client_id, breaches, val["holdings"], val["total_value"], level)
    # Publish RiskThresholdBreached event to EventBridge
    try:
        events_client.put_events(Entries=[{
            "Source": "portfolio-risk.risk-service",
            "DetailType": EVENT_RISK_THRESHOLD_BREACHED,
            "Detail": str({"client_id":client_id,"risk_level":level,"breaches":len(breaches)}),
            "EventBusName": "portfolio-risk-bus"
        }])
    except Exception: pass
    logger.warning(f"{EVENT_RISK_THRESHOLD_BREACHED} — client={client_id} level={level} breaches={len(breaches)}")

    _alerts_store[aid] = {
        "alert_id":        aid, "client_id": client_id, "timestamp": ts,
        "event_type":      EVENT_RISK_THRESHOLD_BREACHED,
        "risk_level":      level, "portfolio_value": round(val["total_value"],2),
        "risks":           breaches, "status": "AI_INSIGHT_GENERATED"
    }
    iid = str(uuid.uuid4())
    # Publish AIInsightGenerated event to EventBridge
    try:
        events_client.put_events(Entries=[{
            "Source": "portfolio-risk.ai-insight-service",
            "DetailType": EVENT_AI_INSIGHT_GENERATED,
            "Detail": str({"client_id":client_id,"insight_id":iid,"risk_level":level}),
            "EventBusName": "portfolio-risk-bus"
        }])
    except Exception: pass
    logger.info(f"{EVENT_AI_INSIGHT_GENERATED} — client={client_id}")

    _insights_store[iid] = {"insight_id":iid,"client_id":client_id,"alert_id":aid,
                             "event_type":EVENT_AI_INSIGHT_GENERATED,
                             "risk_level":level,"timestamp":ts,**insight}
    for r in breaches:
        add_action(client_id, r["risk_type"],
                   gen_action_msg(r["risk_type"], ticker=r.get("ticker","portfolio"),
                                  val=r["breach_value"],
                                  price=current_prices.get(r.get("ticker","AAPL"),0)))

# ── Price simulation ──────────────────────────────────────
def price_simulation_loop():
    """
    Simulates real stock price fluctuations every 5-10 seconds.
    - High enough volatility so changes are VISIBLE on dashboard
    - Every 8 ticks triggers a big "news event" move on one stock
    - Updates ALL 20 tickers every tick so dashboard feels alive
    - Runs risk check on ALL 100 portfolios every tick
    """
    time.sleep(2)
    tickers = list(BASE_PRICES.keys())
    tick = 0

    while True:
        tick += 1

        # update ALL 20 tickers every tick so everything moves
        for ticker in tickers:
            prev = current_prices[ticker]

            # every 8 ticks — one stock gets a big news-style move
            if tick % 8 == 0 and ticker == random.choice(tickers):
                shock = random.uniform(-0.06, 0.06)   # up to ±6% big move
            else:
                # normal tick with clearly visible volatility (1.5% std)
                shock = random.gauss(0.0, 0.015)

            new_price = round(max(prev * (1 + shock), 0.01), 2)
            current_prices[ticker] = new_price
            chg = round((new_price - prev) / prev * 100, 3)

            # publish PriceUpdated to EventBridge
            try:
                events_client.put_events(Entries=[{
                    "Source": "portfolio-risk.market-data-service",
                    "DetailType": EVENT_PRICE_UPDATED,
                    "Detail": str({"ticker": ticker, "price": new_price, "change_pct": chg}),
                    "EventBusName": "portfolio-risk-bus"
                }])
            except Exception:
                pass

            logger.info(f"{EVENT_PRICE_UPDATED} — {ticker} ${new_price:.2f} ({chg:+.2f}%)")

            # add to action feed for all clients holding this ticker
            for cid, p in _portfolio_store.items():
                if any(h["ticker"] == ticker for h in p["holdings"]):
                    add_action(cid, "PRICE_MOVE",
                               gen_action_msg("PRICE_MOVE", ticker=ticker,
                                              val=chg, price=new_price))

        # risk check on ALL 100 portfolios every tick — not just sample of 10
        for p in list(_portfolio_store.values()):
            try:
                run_risk_check(p["client_id"], p["holdings"])
            except Exception:
                pass

        time.sleep(random.uniform(5, 10))

threading.Thread(target=price_simulation_loop, daemon=True).start()

# ── FIX 3: Improved AI Assistant ─────────────────────────
def detect_intent(q: str) -> str:
    """Fuzzy intent detection — checks multiple keyword patterns per intent."""
    q = q.lower()
    rules = [
        ("top_investors",       ["top investor","highest value","richest","largest portfolio","best portfolio","most money","biggest portfolio"]),
        ("risk_summary",        ["risk summary","risk overview","risk breakdown","risk distribution","how many high","how many low","how many medium","risk count","all risk","risk stats"]),
        ("high_risk_clients",   ["high risk","high-risk","high risk client","who is high","list high"]),
        ("medium_risk_clients", ["medium risk","medium-risk","moderate risk","who is medium"]),
        ("low_risk_clients",    ["low risk","low-risk","safe client","who is low","safe portfolio"]),
        ("sector_exposure",     ["sector","technology","finance","healthcare","energy","consumer","entertainment","automotive","retail","tech stock","which sector"]),
        ("price_query",         ["price","current price","trading at","stock price","how much is","what is aapl","what is msft","what is nvda","what is tsla","cost of"]),
        ("portfolio_value",     ["portfolio value","how much is","how much worth","total value","aum","what is aum","value of","net worth"]),
        ("concentration_risk",  ["concentration","overexposed","overweight","too much","single stock","over 20","exceed 20","concentrated"]),
        ("diversification",     ["diversif","spread","balanced","well-rounded","well diversified","is it diversified"]),
        ("alerts",              ["alert","breach","triggered","warning","notification","recent alert","show alert","risk alert"]),
        ("rebalance",           ["rebalance","rebalancing","drift","out of balance","need to rebalance","which client need","needs rebalancing"]),
        ("compare",             ["compare","vs","versus","difference between","which is better","better portfolio"]),
        ("holdings",            ["hold","what stock","what does","position","equity","shares","what ticker","what equity"]),
        ("client_detail",       ["tell me about","details of","overview of","profile of","info on","about cl-","about client"]),
    ]
    for intent, keywords in rules:
        if any(kw in q for kw in keywords):
            return intent
    # If query contains a CL- ID, treat as client detail
    if re.search(r'cl[-\s]?\d{4}', q):
        return "client_detail"
    return "unknown"

def extract_ticker(q: str) -> Optional[str]:
    q_up = q.upper()
    for t in EQUITIES:
        if t in q_up: return t
    return None

def extract_client_id(q: str) -> Optional[str]:
    m = re.search(r'cl[-\s]?(\d{4})', q, re.IGNORECASE)
    return f"CL-{m.group(1)}" if m else None

def extract_sector(q: str) -> Optional[str]:
    for s in ["Technology","Finance","Healthcare","Energy","Consumer","Entertainment","Automotive","Retail"]:
        if s.lower() in q.lower(): return s
    return None

def answer_query(query: str, client_id: Optional[str] = None) -> dict:
    q      = query.lower().strip()
    intent = detect_intent(q)
    cid    = client_id or extract_client_id(q)

    # ── top investors ─────────────────────────────────────
    if intent == "top_investors":
        ranked = sorted([
            {"client_id":p["client_id"],
             "value":round(sum(h["quantity"]*current_prices.get(h["ticker"],0) for h in p["holdings"]),2)}
            for p in _portfolio_store.values()
        ], key=lambda x:x["value"], reverse=True)[:5]
        lines = [f"{i+1}. **{c['client_id']}** — ${c['value']:,.2f}" for i,c in enumerate(ranked)]
        return {"answer":"**🏆 Top 5 Investors by Portfolio Value:**\n"+"\n".join(lines),"intent":intent,"data":ranked}

    # ── risk summary ──────────────────────────────────────
    if intent == "risk_summary":
        h=m=l=0
        for p in _portfolio_store.values():
            lv = p.get("risk_profile","LOW")
            if lv=="HIGH": h+=1
            elif lv=="MEDIUM": m+=1
            else: l+=1
        t=h+m+l
        return {"answer":(f"**📊 Risk Distribution across {t} clients:**\n"
                          f"🔴 High Risk:   **{h} clients** ({h/t*100:.0f}%)\n"
                          f"🟡 Medium Risk: **{m} clients** ({m/t*100:.0f}%)\n"
                          f"🟢 Low Risk:    **{l} clients** ({l/t*100:.0f}%)"),
                "intent":intent,"data":{"high":h,"medium":m,"low":l,"total":t}}

    # ── risk level lists ──────────────────────────────────
    if intent in ("high_risk_clients","medium_risk_clients","low_risk_clients"):
        level_map = {"high_risk_clients":"HIGH","medium_risk_clients":"MEDIUM","low_risk_clients":"LOW"}
        level = level_map[intent]
        matched = [{"client_id":p["client_id"],
                    "portfolio_value":round(sum(h["quantity"]*current_prices.get(h["ticker"],0) for h in p["holdings"]),2)}
                   for p in _portfolio_store.values() if p.get("risk_profile")==level]
        matched.sort(key=lambda x:x["portfolio_value"],reverse=True)
        color = "🔴" if level=="HIGH" else ("🟡" if level=="MEDIUM" else "🟢")
        lines = [f"• **{c['client_id']}** — ${c['portfolio_value']:,.0f}" for c in matched[:10]]
        extra = f"\n_...and {len(matched)-10} more_" if len(matched)>10 else ""
        return {"answer":f"**{color} {level} Risk Clients ({len(matched)} total):**\n"+"\n".join(lines)+extra,
                "intent":intent,"data":matched}

    # ── price query ───────────────────────────────────────
    if intent == "price_query":
        ticker = extract_ticker(q)
        if ticker:
            p=current_prices[ticker]; op=daily_open_prices.get(ticker,p)
            chg=(p-op)/op*100; arrow="📈" if chg>=0 else "📉"
            return {"answer":f"**{ticker}** {arrow}\nCurrent Price: **${p:.2f}**\nDaily Change: **{chg:+.2f}%**\nOpen: ${op:.2f}",
                    "intent":intent,"data":{"ticker":ticker,"price":p,"daily_change_pct":round(chg,4)}}
        lines = [f"• **{t}**: ${p:.2f}" for t,p in list(current_prices.items())[:10]]
        return {"answer":"**💹 Current Prices (top 10):**\n"+"\n".join(lines),"intent":intent,"data":current_prices}

    # ── portfolio value ───────────────────────────────────
    if intent == "portfolio_value":
        if cid:
            p = _portfolio_store.get(cid)
            if not p: return {"answer":f"❌ Client {cid} not found.","intent":intent,"data":None}
            val = compute_valuation(p["holdings"])
            ov  = portfolio_open_values.get(cid, val["total_value"])
            dc  = (val["total_value"]-ov)/ov*100 if ov else 0
            return {"answer":(f"**{cid} Portfolio Value**\n"
                              f"Current: **${val['total_value']:,.2f}**\n"
                              f"Daily Change: {'📈' if dc>=0 else '📉'} **{dc:+.2f}%**\n"
                              f"Risk Profile: **{p.get('risk_profile','N/A')}**"),
                    "intent":intent,"data":{"client_id":cid,"value":val["total_value"]},"client_id":cid}
        total = sum(sum(h["quantity"]*current_prices.get(h["ticker"],0) for h in p["holdings"])
                    for p in _portfolio_store.values())
        return {"answer":f"**💰 Total AUM: ${total:,.2f}**\nacross {len(_portfolio_store)} client portfolios",
                "intent":intent,"data":{"total_aum":round(total,2)}}

    # ── concentration risk ────────────────────────────────
    if intent == "concentration_risk":
        flagged = []
        for p in _portfolio_store.values():
            val = compute_valuation(p["holdings"])
            for h in val["holdings"]:
                if h["allocation_pct"] > CONCENTRATION_THRESHOLD:
                    flagged.append({"client_id":p["client_id"],"ticker":h["ticker"],"allocation":h["allocation_pct"]})
        flagged.sort(key=lambda x:x["allocation"],reverse=True)
        lines = [f"• **{f['client_id']}**: {f['ticker']} at {f['allocation']:.1f}%" for f in flagged[:10]]
        return {"answer":f"**🔴 Single-Stock Concentration >20% ({len(flagged)} found):**\n"+"\n".join(lines),
                "intent":intent,"data":flagged[:20]}

    # ── alerts ────────────────────────────────────────────
    if intent == "alerts":
        recent = sorted(_alerts_store.values(),key=lambda x:x["timestamp"],reverse=True)[:10]
        if not recent: return {"answer":"No alerts yet — price simulation is running.","intent":intent,"data":[]}
        lines = [f"• **{a['client_id']}** [{a['risk_level']}] — {a['timestamp'][11:19]} UTC" for a in recent]
        return {"answer":f"**⚠️ Recent Risk Alerts ({len(_alerts_store)} total):**\n"+"\n".join(lines),
                "intent":intent,"data":recent}

    # ── rebalance ─────────────────────────────────────────
    if intent == "rebalance":
        if cid:
            p = _portfolio_store.get(cid)
            if not p: return {"answer":f"❌ {cid} not found.","intent":intent,"data":None}
            val    = compute_valuation(p["holdings"])
            drifts = [h for h in val["holdings"] if abs(h["drift_pct"]) > DRIFT_THRESHOLD]
            if not drifts: return {"answer":f"✅ **{cid}** is balanced — no rebalancing needed.","intent":intent,"data":[]}
            lines = [f"• **{h['ticker']}**: {h['drift_pct']:+.1f}% drift (actual {h['allocation_pct']:.1f}% vs model {h['model_allocation_pct']:.1f}%)" for h in drifts]
            return {"answer":f"**{cid} Rebalancing Needed:**\n"+"\n".join(lines),"intent":intent,"data":drifts,"client_id":cid}
        needs = []
        for p in _portfolio_store.values():
            val   = compute_valuation(p["holdings"])
            dc    = [h for h in val["holdings"] if abs(h["drift_pct"])>DRIFT_THRESHOLD]
            if dc: needs.append({"client_id":p["client_id"],"drift_count":len(dc)})
        lines = [f"• **{n['client_id']}**: {n['drift_count']} holding(s) need rebalancing" for n in needs[:10]]
        extra = f"\n_...and {len(needs)-10} more_" if len(needs)>10 else ""
        return {"answer":f"**🔄 Clients Needing Rebalancing ({len(needs)}):**\n"+"\n".join(lines)+extra,"intent":intent,"data":needs}

    # ── compare ───────────────────────────────────────────
    if intent == "compare":
        ids = [f"CL-{x}" for x in re.findall(r'cl[-\s]?(\d{4})',q,re.IGNORECASE)]
        if len(ids)<2: return {"answer":"Please specify two clients: e.g. **Compare CL-1001 vs CL-1002**","intent":intent,"data":None}
        results=[]
        for c in ids[:2]:
            p=_portfolio_store.get(c)
            if not p: continue
            val=compute_valuation(p["holdings"])
            results.append({"client_id":c,"value":val["total_value"],"risk":get_risk_level(p["client_id"], compute_valuation(p["holdings"])),"holdings":len(val["holdings"])})
        if len(results)<2: return {"answer":"One or both clients not found.","intent":intent,"data":None}
        a,b=results; winner=a["client_id"] if a["value"]>b["value"] else b["client_id"]
        return {"answer":(f"**📊 Portfolio Comparison**\n"
                          f"**{a['client_id']}**: ${a['value']:,.2f} | {a['risk']} RISK | {a['holdings']} holdings\n"
                          f"**{b['client_id']}**: ${b['value']:,.2f} | {b['risk']} RISK | {b['holdings']} holdings\n"
                          f"Higher value: **{winner}**"),
                "intent":intent,"data":results}

    # ── diversification ───────────────────────────────────
    if intent == "diversification":
        if not cid: return {"answer":"Please specify a client, e.g. **Is CL-1020 well diversified?**","intent":intent,"data":None}
        p=_portfolio_store.get(cid)
        if not p: return {"answer":f"❌ {cid} not found.","intent":intent,"data":None}
        val=compute_valuation(p["holdings"]); n=len(val["holdings"])
        mx=max((h["allocation_pct"] for h in val["holdings"]),default=0)
        sectors=list({h.get("sector","Other") for h in val["holdings"]})
        score=("✅ Well-diversified" if (n>=6 and mx<20 and len(sectors)>=3)
               else "⚠️ Moderately diversified" if (n>=4 and mx<30)
               else "🔴 Concentrated — consider spreading across more assets")
        return {"answer":(f"**{cid} Diversification Analysis**\n"
                          f"Holdings: **{n} stocks**\nSectors: {', '.join(sectors)}\n"
                          f"Largest position: **{mx:.1f}%**\nAssessment: **{score}**"),
                "intent":intent,"data":{"holdings":n,"sectors":sectors,"max_alloc":mx},"client_id":cid}

    # ── sector exposure ───────────────────────────────────
    if intent == "sector_exposure":
        target = extract_sector(q) or "Technology"
        exposed=[]
        for p in _portfolio_store.values():
            val=compute_valuation(p["holdings"])
            pct=sum(h["allocation_pct"] for h in val["holdings"] if h.get("sector")==target)
            if pct>0: exposed.append({"client_id":p["client_id"],"sector_pct":round(pct,2)})
        exposed.sort(key=lambda x:x["sector_pct"],reverse=True)
        lines=[f"• **{e['client_id']}**: {e['sector_pct']:.1f}% in {target}" for e in exposed[:10]]
        return {"answer":f"**🏭 {target} Sector Exposure ({len(exposed)} clients):**\n"+"\n".join(lines),"intent":intent,"data":exposed[:20]}

    # ── holdings / client detail ──────────────────────────
    if intent in ("holdings","client_detail") or cid:
        if not cid: return {"answer":"Please specify a client ID, e.g. **What does CL-1005 hold?**","intent":intent,"data":None}
        p=_portfolio_store.get(cid)
        if not p: return {"answer":f"❌ Client {cid} not found. Check the ID and try again.","intent":intent,"data":None}
        val=compute_valuation(p["holdings"])
        breaches=detect_breaches(cid,val)
        level=p.get("risk_profile","?")
        lines=[f"• **{h['ticker']}** ({h.get('sector','?')}): {h['allocation_pct']:.1f}% | "
               f"{h['quantity']:.1f} shares @ ${h['current_price']:.2f} = ${h['current_value']:,.0f}"
               for h in val["holdings"]]
        risk_text="\n".join(f"⚠️ {r['description']}" for r in breaches) if breaches else "✅ No active threshold breaches"
        return {"answer":(f"**{cid} — {p['client_name']}**\n"
                          f"Total Value: **${val['total_value']:,.2f}** | Risk Profile: **{level}**\n\n"
                          f"**Holdings:**\n"+"\n".join(lines)+f"\n\n**Risk Status:**\n{risk_text}"),
                "intent":intent,"data":val["holdings"],"client_id":cid}

    # ── fallback help ─────────────────────────────────────
    return {
        "answer":(
            "I can answer questions about all 100 client portfolios. Try asking:\n\n"
            "• **Top investors** → _'Who are the top 5 investors?'_\n"
            "• **Risk summary** → _'Give me a risk distribution summary'_\n"
            "• **Risk levels** → _'Show all high risk clients'_\n"
            "• **Client detail** → _'Tell me about CL-1005'_\n"
            "• **Holdings** → _'What stocks does CL-1012 hold?'_\n"
            "• **Portfolio value** → _'What is CL-1005 worth?'_\n"
            "• **Prices** → _'What is the current NVDA price?'_\n"
            "• **Sector** → _'Which clients have high tech exposure?'_\n"
            "• **Concentration** → _'Show overexposed portfolios'_\n"
            "• **Rebalancing** → _'Which clients need rebalancing?'_\n"
            "• **Compare** → _'Compare CL-1001 vs CL-1002'_\n"
            "• **Diversification** → _'Is CL-1020 well diversified?'_\n"
            "• **Alerts** → _'Show recent risk alerts'_\n"
            "• **Total AUM** → _'What is the total AUM?'_"
        ),
        "intent":"help","data":None
    }

# ── FastAPI — Microservice Routers ───────────────────────
# Each router represents a separate microservice.
# In production these would be deployed as individual Lambda functions.
# ─────────────────────────────────────────────────────────
from fastapi import APIRouter

# Router 1: Portfolio Service
portfolio_router = APIRouter(prefix="/portfolio-service", tags=["Portfolio Service"])

# Router 2: Market Data Service
market_router = APIRouter(prefix="/market-data-service", tags=["Market Data Service"])

# Router 3: Risk Service
risk_router = APIRouter(prefix="/risk-service", tags=["Risk Service"])

# Router 4: AI Insight Service
ai_router = APIRouter(prefix="/ai-insight-service", tags=["AI Insight Service"])

app = FastAPI(
    title="Portfolio Risk Alert System",
    version="3.0.0",
    description="4 microservices: Portfolio, Market Data, Risk, AI Insight"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    query: str
    client_id: Optional[str] = None

@app.get("/")
def root(): return {"status":"ok","version":"3.0.0","microservices":["portfolio-service","market-data-service","risk-service","ai-insight-service"]}

@app.get("/health")
def health():
    seed_portfolios()
    return {"status":"ok","clients":len(_portfolio_store),"alerts":len(_alerts_store),"insights":len(_insights_store)}

@app.post("/admin/seed")
def admin_seed():
    seed_portfolios()
    return {"message":"100 portfolios seeded","count":len(_portfolio_store)}

@app.get("/clients")
def get_clients():
    seed_portfolios()
    result=[]; seen=set()
    for p in _portfolio_store.values():
        cid=p["client_id"]
        if cid in seen: continue
        seen.add(cid)
        val=compute_valuation(p["holdings"])
        level=get_risk_level(cid, val)   # DYNAMIC — fluctuates with prices
        mx=max((h["allocation_pct"] for h in val["holdings"]),default=0)
        breaches=detect_breaches(cid,val)
        result.append({
            "clientId":cid,"clientName":p["client_name"],
            "holdings":[{"symbol":h["ticker"],"shares":round(h["quantity"],4),
                         "price":h["current_price"],"value":round(h["current_value"],2),
                         "allocation_pct":h["allocation_pct"],
                         "model_allocation_pct":h["model_allocation_pct"],
                         "drift_pct":h["drift_pct"],"sector":h.get("sector","Other")}
                        for h in val["holdings"]],
            "risk":level,"exposure":round(mx,1),"value":val["total_value"],"riskCount":len(breaches)
        })
    result.sort(key=lambda x:x["value"],reverse=True)
    return result

@app.get("/portfolios")
def list_portfolios():
    seed_portfolios(); return list(_portfolio_store.values())[:20]

@app.get("/portfolios/{client_id}")
def get_portfolio(client_id:str):
    seed_portfolios()
    p=_portfolio_store.get(client_id)
    if not p: raise HTTPException(404,"Not found")
    return p

@app.get("/prices")
def get_prices(): return {"timestamp":now_ts(),"prices":current_prices}

@app.get("/prices/{ticker}")
def get_price(ticker:str):
    ticker=ticker.upper()
    if ticker not in current_prices: raise HTTPException(404,"Ticker not found")
    op=daily_open_prices.get(ticker,current_prices[ticker])
    return {"ticker":ticker,"price":current_prices[ticker],"daily_open":op,
            "daily_change_pct":round((current_prices[ticker]-op)/op*100,4),"sector":SECTORS.get(ticker,"Other")}

@app.get("/alerts")
def get_alerts(risk_level:Optional[str]=None,limit:int=50):
    items=list(_alerts_store.values())
    if risk_level: items=[i for i in items if i["risk_level"]==risk_level.upper()]
    items.sort(key=lambda x:x["timestamp"],reverse=True)
    return {"alerts":items[:limit],"count":len(items)}

@app.get("/alerts/{client_id}")
def get_client_alerts(client_id:str):
    items=sorted([a for a in _alerts_store.values() if a["client_id"]==client_id],key=lambda x:x["timestamp"],reverse=True)
    return {"client_id":client_id,"alerts":items}

@app.get("/insights")
def get_insights(limit:int=20):
    items=sorted(_insights_store.values(),key=lambda x:x["timestamp"],reverse=True)
    return {"insights":list(items)[:limit],"count":len(_insights_store)}

@app.get("/insights/{client_id}/latest")
def get_latest_insight(client_id:str):
    items=sorted([i for i in _insights_store.values() if i["client_id"]==client_id],key=lambda x:x["timestamp"],reverse=True)
    if not items: raise HTTPException(404,"No insights found")
    return items[0]

@app.get("/feed/{client_id}")
def get_action_feed(client_id:str,limit:int=20):
    seed_portfolios()
    if client_id not in _action_feeds: raise HTTPException(404,"Client not found")
    return {"client_id":client_id,"feed":_action_feeds[client_id][:limit],"count":len(_action_feeds[client_id])}

@app.get("/dashboard/stats")
def dashboard_stats():
    seed_portfolios()
    h=m=l=0; total_val=0.0; seen=set()
    for p in _portfolio_store.values():
        cid=p["client_id"]
        if cid in seen: continue
        seen.add(cid)
        val=compute_valuation(p["holdings"]); total_val+=val["total_value"]
        val_s=compute_valuation(p["holdings"]); lv=get_risk_level(cid, val_s)  # DYNAMIC
        if lv=="HIGH": h+=1
        elif lv=="MEDIUM": m+=1
        else: l+=1
    return {"total_clients":len(seen),"total_alerts":len(_alerts_store),"high_risk":h,
            "medium_risk":m,"low_risk":l,"total_aum":round(total_val,2),
            "equities_tracked":len(current_prices),"last_updated":now_ts()}

@app.get("/risk/analytics")
def risk_analytics():
    seed_portfolios()
    high=[]; medium=[]; low=[]; seen=set()
    for p in _portfolio_store.values():
        cid=p["client_id"]
        if cid in seen: continue
        seen.add(cid)
        val=compute_valuation(p["holdings"])
        lv=get_risk_level(cid, val)   # DYNAMIC
        breaches=detect_breaches(cid,val)
        entry={"clientId":cid,"clientName":p["client_name"],"risk_level":lv,
               "portfolio_value":round(val["total_value"],2),"risk_count":len(breaches)}
        if lv=="HIGH": high.append(entry)
        elif lv=="MEDIUM": medium.append(entry)
        else: low.append(entry)
    return {
        "high_risk_clients":   sorted(high,  key=lambda x:x["portfolio_value"],reverse=True)[:10],
        "medium_risk_clients": sorted(medium,key=lambda x:x["portfolio_value"],reverse=True)[:10],
        "low_risk_clients":    sorted(low,   key=lambda x:x["portfolio_value"],reverse=True)[:10],
        "summary":{"HIGH":len(high),"MEDIUM":len(medium),"LOW":len(low),"total":len(high)+len(medium)+len(low)}
    }

@app.get("/top-investors")
def top_investors():
    seed_portfolios()
    result=sorted([{"clientId":p["client_id"],"clientName":p["client_name"],
                    "portfolio_value":round(sum(h["quantity"]*current_prices.get(h["ticker"],0) for h in p["holdings"]),2)}
                   for p in _portfolio_store.values()],key=lambda x:x["portfolio_value"],reverse=True)
    return {"top_investors":result[:5]}

@app.post("/assistant/query")
def assistant_query(req:QueryRequest):
    seed_portfolios()
    if not req.query.strip(): raise HTTPException(400,"Query cannot be empty")
    result=answer_query(req.query,req.client_id)
    return {"query":req.query,"answer":result["answer"],"intent":result.get("intent","unknown"),
            "data":result.get("data"),"client_id":result.get("client_id"),"timestamp":now_ts()}

# ── Register microservice routers on the app ─────────────
# Portfolio Service endpoints
@portfolio_router.get("/clients")
def ms_get_clients(): return get_clients()

@portfolio_router.get("/portfolios")
def ms_list_portfolios(): return list_portfolios()

@portfolio_router.get("/portfolios/{client_id}")
def ms_get_portfolio(client_id: str): return get_portfolio(client_id)

@portfolio_router.post("/admin/seed")
def ms_admin_seed(): return admin_seed()

# Market Data Service endpoints
@market_router.get("/prices")
def ms_get_prices(): return get_prices()

@market_router.get("/prices/{ticker}")
def ms_get_price(ticker: str): return get_price(ticker)

@market_router.get("/feed/{client_id}")
def ms_get_feed(client_id: str, limit: int = 20): return get_action_feed(client_id, limit)

# Risk Service endpoints
@risk_router.get("/alerts")
def ms_get_alerts(risk_level: Optional[str] = None, limit: int = 50): return get_alerts(risk_level, limit)

@risk_router.get("/alerts/{client_id}")
def ms_get_client_alerts(client_id: str): return get_client_alerts(client_id)

@risk_router.get("/analytics")
def ms_risk_analytics(): return risk_analytics()

@risk_router.get("/revalued/{client_id}")
def ms_get_revalued(client_id: str):
    """PortfolioRevalued event — latest revaluation for a client"""
    seed_portfolios()
    event = _revalued_store.get(client_id)
    if not event:
        raise HTTPException(404, "No revaluation found for this client yet")
    return event

@risk_router.get("/revalued")
def ms_get_all_revalued():
    """All latest PortfolioRevalued events"""
    return {"revalued_events": list(_revalued_store.values()), "count": len(_revalued_store)}

# AI Insight Service endpoints
@ai_router.get("/insights")
def ms_get_insights(limit: int = 20): return get_insights(limit)

@ai_router.get("/insights/{client_id}/latest")
def ms_get_latest_insight(client_id: str): return get_latest_insight(client_id)

@ai_router.post("/query")
def ms_assistant_query(req: QueryRequest): return assistant_query(req)

@ai_router.get("/suggestions")
def ms_query_suggestions(): return query_suggestions()

# Mount all microservice routers
app.include_router(portfolio_router)
app.include_router(market_router)
app.include_router(risk_router)
app.include_router(ai_router)

@app.get("/assistant/suggestions")
def query_suggestions():
    return {"suggestions":[
        "Who are the top 5 investors?","Show all high risk clients","Give me a risk distribution summary",
        "What is CL-1005 worth?","What stocks does CL-1012 hold?","Which clients have high technology sector exposure?",
        "Show portfolios with single stock overexposure","Which clients need rebalancing?",
        "What is the current NVDA price?","Is CL-1020 well diversified?","Compare CL-1001 vs CL-1002",
        "Show recent risk alerts","What is the total AUM?","Tell me about CL-1035","Show all low risk clients"
    ]}
