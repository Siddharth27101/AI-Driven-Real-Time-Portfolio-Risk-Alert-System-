# AI-Driven Real-Time Portfolio Risk Alert System

A real-time portfolio monitoring system that detects investment risks and generates AI-powered insights using AWS services and Amazon Bedrock.

---

## 🚀 Quick Start

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open:
```text
http://localhost:3000
```

---

# 📌 Project Overview

This system continuously monitors investment portfolios and detects:

- Portfolio concentration risks
- Allocation drift
- Risk threshold breaches

When risks are detected, the system generates human-readable AI insights and recommendations.

---

# 🏗️ Architecture Flow

```text
Market Data Service
        ↓
PriceUpdated Event
        ↓
Risk Service
        ↓
RiskThresholdBreached Event
        ↓
AI Insight Service
        ↓
Dashboard Updates
```

---

# ⚙️ Design Decisions

## Python + FastAPI
- Fast API performance
- Async support
- Easy AWS integration using boto3
- Pydantic validation

## Rule-Based + AI Hybrid
- Python handles risk calculations
- Amazon Bedrock generates readable investment insights
- Ensures reliable calculations with user-friendly AI explanations

## Local AWS Mocking
Uses **moto** to mock:
- DynamoDB
- SQS
- EventBridge

This allows local execution without real AWS setup.

---

# 📊 Portfolio Types

| Risk Level | Behavior |
|---|---|
| HIGH | Large holdings causing concentration risk |
| MEDIUM | Balanced holdings with slight drift |
| LOW | Well-diversified portfolios |

---

# 📈 Scaling Strategy

To support large-scale users:
- AWS Lambda auto scaling
- Redis shared caching
- DynamoDB Streams optimization
- SQS queue buffering
- CloudWatch monitoring

---

# 🤖 AI Prompt Approach

## Model Used
Amazon Bedrock — Claude 3 Sonnet

## Prompt Strategy
The AI receives:
- Client portfolio value
- Risk level
- Breach details
- Stock percentages
- Dollar values

The model then generates structured investment insights in simple human-readable language.

## AI Generates
- Risk explanations
- Suggested actions
- Severity reasoning
- Advisory disclaimers

## Why This Approach Works
Providing exact percentages and investment values helps the AI generate:
- accurate explanations
- meaningful recommendations
- less generic financial advice

---

# ☁️ AWS Services Used

| Service | Purpose |
|---|---|
| API Gateway | REST APIs |
| AWS Lambda | Backend compute |
| DynamoDB | Portfolio storage |
| EventBridge | Event routing |
| SQS | Queue management |
| CloudWatch | Monitoring |
| Bedrock | AI insight generation |
| CDK | Infrastructure deployment |

---

# ✅ Features

- Real-time portfolio monitoring
- AI-generated investment insights
- Event-driven architecture
- Risk threshold alerts
- Scalable AWS-native design
- Local AWS mocking support

---

# 🔮 Future Enhancements

- WebSocket live updates
- Multi-region deployment
- Advanced analytics
- User authentication

---

# 📄 License

This project is created for educational and demonstration purposes.
