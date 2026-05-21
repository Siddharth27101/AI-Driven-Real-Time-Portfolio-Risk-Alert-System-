"""
schemas/events.py
=================
Clearly defined JSON schemas for all 4 events in the
AI-Driven Portfolio Risk Alert System.

Required by spec:
  • PriceUpdated
  • PortfolioRevalued
  • RiskThresholdBreached
  • AIInsightGenerated

Each event has:
  1. Pydantic model (Python schema + validation)
  2. JSON Schema dict  (for API documentation)
  3. Concrete JSON example (for demo / evaluator)
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import json


# ─────────────────────────────────────────────────────────
# Shared Enums
# ─────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"

class RiskType(str, Enum):
    ALLOCATION_DRIFT           = "ALLOCATION_DRIFT"
    SINGLE_STOCK_OVEREXPOSURE  = "SINGLE_STOCK_OVEREXPOSURE"
    DAILY_DROP                 = "DAILY_DROP"


# ─────────────────────────────────────────────────────────
# Shared Sub-Models
# ─────────────────────────────────────────────────────────

class RiskBreach(BaseModel):
    """A single risk threshold breach detected in a portfolio."""
    risk_type:       RiskType = Field(..., description="Type of risk breach detected")
    ticker:          Optional[str] = Field(None, description="Stock ticker involved, null for portfolio-level events")
    breach_value:    float = Field(..., description="The actual value that breached the threshold")
    threshold_value: float = Field(..., description="The configured threshold limit")
    description:     str   = Field(..., description="Human-readable description of the breach")

class HoldingSnapshot(BaseModel):
    """Point-in-time snapshot of a single stock holding."""
    ticker:                str   = Field(..., description="Stock ticker symbol e.g. AAPL")
    quantity:              float = Field(..., description="Number of shares held")
    current_price:         float = Field(..., description="Current market price per share in USD")
    current_value:         float = Field(..., description="Total value of this holding (quantity × price)")
    allocation_pct:        float = Field(..., description="Actual % of portfolio this holding represents")
    model_allocation_pct:  float = Field(..., description="Target % from the model portfolio")
    drift_pct:             float = Field(..., description="Difference: actual% - model% (positive = overweight)")
    sector:                str   = Field(..., description="Business sector e.g. Technology, Finance")


# ─────────────────────────────────────────────────────────
# EVENT 1: PriceUpdated
# Published by: Market Data Service
# Consumed by:  Risk Service
# Trigger:      Every 5–10 seconds per ticker
# ─────────────────────────────────────────────────────────

class PriceUpdated(BaseModel):
    """
    Published by the Market Data Service every 5–10 seconds
    when a stock price changes. Triggers portfolio revaluation
    in the Risk Service.
    """
    event_id:       str      = Field(..., description="Unique event identifier (UUID)")
    event_type:     str      = Field("PriceUpdated", description="Always 'PriceUpdated'")
    timestamp:      str      = Field(..., description="ISO 8601 UTC timestamp with timezone e.g. 2024-01-15T10:30:00+00:00")
    source:         str      = Field("market-data-service", description="Originating microservice")
    ticker:         str      = Field(..., description="Stock ticker symbol e.g. AAPL")
    price:          float    = Field(..., description="New current price in USD")
    previous_price: float    = Field(..., description="Previous price before this update")
    change_pct:     float    = Field(..., description="Percentage change from previous price")
    sector:         str      = Field(..., description="Business sector of the equity")

PRICE_UPDATED_JSON_SCHEMA = {
    "type": "object",
    "title": "PriceUpdated",
    "description": "Emitted by Market Data Service when a stock price changes",
    "required": ["event_id","event_type","timestamp","source","ticker","price","previous_price","change_pct"],
    "properties": {
        "event_id":       {"type": "string",  "format": "uuid"},
        "event_type":     {"type": "string",  "enum": ["PriceUpdated"]},
        "timestamp":      {"type": "string",  "format": "date-time"},
        "source":         {"type": "string"},
        "ticker":         {"type": "string",  "example": "AAPL"},
        "price":          {"type": "number",  "minimum": 0},
        "previous_price": {"type": "number",  "minimum": 0},
        "change_pct":     {"type": "number"},
        "sector":         {"type": "string"}
    }
}

PRICE_UPDATED_EXAMPLE = {
    "event_id":       "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "event_type":     "PriceUpdated",
    "timestamp":      "2024-01-15T10:30:05+00:00",
    "source":         "market-data-service",
    "ticker":         "AAPL",
    "price":          187.45,
    "previous_price": 185.50,
    "change_pct":     1.051,
    "sector":         "Technology"
}


# ─────────────────────────────────────────────────────────
# EVENT 2: PortfolioRevalued
# Published by: Risk Service
# Consumed by:  Dashboard, Risk threshold checker
# Trigger:      After every PriceUpdated event
# ─────────────────────────────────────────────────────────

class PortfolioRevalued(BaseModel):
    """
    Published by the Risk Service after recomputing a client's
    portfolio value following a price update. Includes full
    holdings snapshot and daily performance.
    """
    event_id:              str                  = Field(..., description="Unique event identifier (UUID)")
    event_type:            str                  = Field("PortfolioRevalued", description="Always 'PortfolioRevalued'")
    timestamp:             str                  = Field(..., description="ISO 8601 UTC timestamp")
    source:                str                  = Field("risk-service", description="Originating microservice")
    client_id:             str                  = Field(..., description="Client identifier e.g. CL-1005")
    total_value:           float                = Field(..., description="Current total portfolio value in USD")
    previous_total_value:  float                = Field(..., description="Portfolio value before this revaluation")
    daily_change_pct:      float                = Field(..., description="Portfolio % change since market open today")
    holdings_count:        int                  = Field(..., description="Number of holdings in the portfolio")

PORTFOLIO_REVALUED_JSON_SCHEMA = {
    "type": "object",
    "title": "PortfolioRevalued",
    "description": "Emitted by Risk Service after every portfolio revaluation",
    "required": ["event_id","event_type","timestamp","source","client_id","total_value","previous_total_value","daily_change_pct"],
    "properties": {
        "event_id":             {"type": "string", "format": "uuid"},
        "event_type":           {"type": "string", "enum": ["PortfolioRevalued"]},
        "timestamp":            {"type": "string", "format": "date-time"},
        "source":               {"type": "string"},
        "client_id":            {"type": "string", "example": "CL-1005"},
        "total_value":          {"type": "number", "minimum": 0},
        "previous_total_value": {"type": "number", "minimum": 0},
        "daily_change_pct":     {"type": "number"},
        "holdings_count":       {"type": "integer", "minimum": 1}
    }
}

PORTFOLIO_REVALUED_EXAMPLE = {
    "event_id":             "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "event_type":           "PortfolioRevalued",
    "timestamp":            "2024-01-15T10:30:06+00:00",
    "source":               "risk-service",
    "client_id":            "CL-1005",
    "total_value":          142350.75,
    "previous_total_value": 140200.00,
    "daily_change_pct":     1.533,
    "holdings_count":       6
}


# ─────────────────────────────────────────────────────────
# EVENT 3: RiskThresholdBreached
# Published by: Risk Service
# Consumed by:  AI Insight Service, Notification Service
# Trigger:      When any of the 3 risk thresholds are exceeded
#   - Allocation drift > 5%
#   - Single stock exposure > 20%
#   - Daily portfolio drop > 3%
# ─────────────────────────────────────────────────────────

class RiskThresholdBreached(BaseModel):
    """
    Published by the Risk Service when one or more risk thresholds
    are breached in a client portfolio. Triggers AI insight generation.
    """
    event_id:        str            = Field(..., description="Unique event identifier (UUID)")
    event_type:      str            = Field("RiskThresholdBreached", description="Always 'RiskThresholdBreached'")
    timestamp:       str            = Field(..., description="ISO 8601 UTC timestamp")
    source:          str            = Field("risk-service", description="Originating microservice")
    client_id:       str            = Field(..., description="Affected client identifier e.g. CL-1042")
    portfolio_value: float          = Field(..., description="Current total portfolio value in USD at time of breach")
    risk_level:      RiskLevel      = Field(..., description="Overall risk classification: LOW / MEDIUM / HIGH")
    breaches:        List[RiskBreach] = Field(..., description="List of all threshold breaches detected")

RISK_THRESHOLD_BREACHED_JSON_SCHEMA = {
    "type": "object",
    "title": "RiskThresholdBreached",
    "description": "Emitted by Risk Service when portfolio risk thresholds are exceeded",
    "required": ["event_id","event_type","timestamp","source","client_id","portfolio_value","risk_level","breaches"],
    "properties": {
        "event_id":        {"type": "string", "format": "uuid"},
        "event_type":      {"type": "string", "enum": ["RiskThresholdBreached"]},
        "timestamp":       {"type": "string", "format": "date-time"},
        "source":          {"type": "string"},
        "client_id":       {"type": "string", "example": "CL-1042"},
        "portfolio_value": {"type": "number", "minimum": 0},
        "risk_level":      {"type": "string", "enum": ["LOW","MEDIUM","HIGH"]},
        "breaches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["risk_type","breach_value","threshold_value","description"],
                "properties": {
                    "risk_type":       {"type": "string", "enum": ["ALLOCATION_DRIFT","SINGLE_STOCK_OVEREXPOSURE","DAILY_DROP"]},
                    "ticker":          {"type": ["string","null"]},
                    "breach_value":    {"type": "number"},
                    "threshold_value": {"type": "number"},
                    "description":     {"type": "string"}
                }
            }
        }
    }
}

RISK_THRESHOLD_BREACHED_EXAMPLE = {
    "event_id":        "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "event_type":      "RiskThresholdBreached",
    "timestamp":       "2024-01-15T10:30:07+00:00",
    "source":          "risk-service",
    "client_id":       "CL-1042",
    "portfolio_value": 98500.00,
    "risk_level":      "HIGH",
    "breaches": [
        {
            "risk_type":       "SINGLE_STOCK_OVEREXPOSURE",
            "ticker":          "NVDA",
            "breach_value":    28.5,
            "threshold_value": 20.0,
            "description":     "NVDA is 28.5% of portfolio, exceeding the 20% single-stock limit"
        },
        {
            "risk_type":       "ALLOCATION_DRIFT",
            "ticker":          "AAPL",
            "breach_value":    -7.2,
            "threshold_value": 5.0,
            "description":     "AAPL drifted -7.2% from model allocation"
        },
        {
            "risk_type":       "DAILY_DROP",
            "ticker":          None,
            "breach_value":    -3.8,
            "threshold_value": -3.0,
            "description":     "Portfolio dropped 3.8% today"
        }
    ]
}


# ─────────────────────────────────────────────────────────
# EVENT 4: AIInsightGenerated
# Published by: AI Insight Service
# Consumed by:  Dashboard, Notification Service
# Trigger:      After processing every RiskThresholdBreached event
# ─────────────────────────────────────────────────────────

class AIInsightGenerated(BaseModel):
    """
    Published by the AI Insight Service after generating a
    plain-language risk explanation and rebalancing suggestion
    using Amazon Bedrock (Claude model).
    """
    event_id:           str       = Field(..., description="Unique event identifier (UUID)")
    event_type:         str       = Field("AIInsightGenerated", description="Always 'AIInsightGenerated'")
    timestamp:          str       = Field(..., description="ISO 8601 UTC timestamp")
    source:             str       = Field("ai-insight-service", description="Originating microservice")
    client_id:          str       = Field(..., description="Client this insight was generated for")
    risk_event_id:      str       = Field(..., description="ID of the RiskThresholdBreached event that triggered this")
    risk_level:         RiskLevel = Field(..., description="Risk classification: LOW / MEDIUM / HIGH")
    explanation:        str       = Field(..., description="Plain-language AI explanation of what is happening in the portfolio")
    suggested_action:   str       = Field(..., description="Specific rebalancing action the investor should consider")
    severity_reasoning: str       = Field(..., description="Why this risk level was assigned")
    disclaimer:         str       = Field(..., description="Mandatory financial advisory disclaimer")

AI_INSIGHT_GENERATED_JSON_SCHEMA = {
    "type": "object",
    "title": "AIInsightGenerated",
    "description": "Emitted by AI Insight Service after Amazon Bedrock generates a portfolio insight",
    "required": ["event_id","event_type","timestamp","source","client_id","risk_event_id","risk_level","explanation","suggested_action","disclaimer"],
    "properties": {
        "event_id":           {"type": "string", "format": "uuid"},
        "event_type":         {"type": "string", "enum": ["AIInsightGenerated"]},
        "timestamp":          {"type": "string", "format": "date-time"},
        "source":             {"type": "string"},
        "client_id":          {"type": "string"},
        "risk_event_id":      {"type": "string", "format": "uuid"},
        "risk_level":         {"type": "string", "enum": ["LOW","MEDIUM","HIGH"]},
        "explanation":        {"type": "string", "minLength": 10},
        "suggested_action":   {"type": "string", "minLength": 10},
        "severity_reasoning": {"type": "string"},
        "disclaimer":         {"type": "string"}
    }
}

AI_INSIGHT_GENERATED_EXAMPLE = {
    "event_id":           "d4e5f6a7-b8c9-0123-defa-234567890123",
    "event_type":         "AIInsightGenerated",
    "timestamp":          "2024-01-15T10:30:08+00:00",
    "source":             "ai-insight-service",
    "client_id":          "CL-1042",
    "risk_event_id":      "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "risk_level":         "HIGH",
    "explanation":        "Your portfolio has significant concentration in NVDA at 28.5%, exceeding the recommended 20% single-stock limit. Additionally, AAPL has drifted 7.2% below its target allocation due to recent underperformance, and the portfolio has declined 3.8% today — breaching the daily loss threshold.",
    "suggested_action":   "Consider trimming your NVDA position by approximately $8,330 to bring single-stock exposure below 20%. Reallocate proceeds toward AAPL to restore its target weight. Review defensive positions to cushion further intraday declines.",
    "severity_reasoning": "Classified as HIGH due to 3 simultaneous threshold breaches: overexposure, allocation drift, and daily drawdown. Multiple concurrent breaches significantly elevate portfolio risk.",
    "disclaimer":         "⚠️ This is an AI-generated suggestion for informational purposes only and does not constitute financial advice. Please consult a qualified financial advisor before making any investment decisions."
}


# ─────────────────────────────────────────────────────────
# Event Flow Summary
# ─────────────────────────────────────────────────────────

EVENT_FLOW = """
Market Data Service
        │
        │ publishes every 5-10s
        ▼
  [ PriceUpdated ]
        │
        │ consumed by
        ▼
   Risk Service
        │
        ├──► [ PortfolioRevalued ]  ──► Dashboard (live price update)
        │
        └──► [ RiskThresholdBreached ] ──► AI Insight Service
                                                │
                                                │ calls Amazon Bedrock
                                                ▼
                                    [ AIInsightGenerated ] ──► Dashboard
                                                           ──► Notification Service
"""

ALL_SCHEMAS = {
    "PriceUpdated":           PRICE_UPDATED_JSON_SCHEMA,
    "PortfolioRevalued":      PORTFOLIO_REVALUED_JSON_SCHEMA,
    "RiskThresholdBreached":  RISK_THRESHOLD_BREACHED_JSON_SCHEMA,
    "AIInsightGenerated":     AI_INSIGHT_GENERATED_JSON_SCHEMA,
}

ALL_EXAMPLES = {
    "PriceUpdated":           PRICE_UPDATED_EXAMPLE,
    "PortfolioRevalued":      PORTFOLIO_REVALUED_EXAMPLE,
    "RiskThresholdBreached":  RISK_THRESHOLD_BREACHED_EXAMPLE,
    "AIInsightGenerated":     AI_INSIGHT_GENERATED_EXAMPLE,
}

if __name__ == "__main__":
    print("=== Event Schemas ===")
    for name, schema in ALL_SCHEMAS.items():
        print(f"\n--- {name} ---")
        print(json.dumps(schema, indent=2))

    print("\n=== Event Examples ===")
    for name, example in ALL_EXAMPLES.items():
        print(f"\n--- {name} ---")
        print(json.dumps(example, indent=2))

    print("\n=== Event Flow ===")
    print(EVENT_FLOW)
