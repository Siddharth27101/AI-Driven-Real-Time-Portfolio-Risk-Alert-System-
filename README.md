<<<<<<< HEAD
# AI-Driven Portfolio Risk Alert System
## Run Locally — No Docker, No AWS Account Needed

---

## ✅ Prerequisites
- Python 3.8 or above
- Node.js 16 or above
- npm

Check versions:
```
python --version
node --version
npm --version
```

---

## Step 1 — Install Backend Dependencies

```
cd backend
pip install -r requirements.txt
```

---

## Step 2 — Start the Backend

```
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
Seeding 100 portfolios...
✅ 100 portfolios seeded
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Test it:
```
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/clients
curl http://127.0.0.1:8000/prices
```

---

## Step 3 — Start the Frontend

Open a NEW terminal window:

```
cd frontend
npm install
npm run dev
```

Open your browser at: http://localhost:3000

---

## Pages Available

| Page          | URL                        | Description                          |
|---------------|----------------------------|--------------------------------------|
| Dashboard     | http://localhost:3000/     | Live stats, prices, system status    |
| Clients       | http://localhost:3000/clients   | All 100 portfolios + AI insights |
| Risk Analytics| http://localhost:3000/risk | Risk classification + alert table    |
| Top Investors | http://localhost:3000/investors | Top 5 by portfolio value        |
| AI Feed       | http://localhost:3000/feed | Live alerts + AI insight stream      |
| AI Assistant  | http://localhost:3000/assistant | AI commentary per client        |
| AWS Services  | http://localhost:3000/aws  | Architecture overview                |

---

## API Endpoints

| Endpoint                        | Description                    |
|---------------------------------|--------------------------------|
| GET  /health                    | Health check                   |
| GET  /clients                   | All 100 clients with risk data |
| GET  /prices                    | Live prices for 20 equities    |
| GET  /alerts                    | All risk alerts                |
| GET  /insights                  | All AI insights                |
| GET  /insights/{client_id}/latest | Latest insight for client   |
| GET  /dashboard/stats           | Summary statistics             |
| GET  /risk/analytics            | Risk breakdown by level        |
| GET  /top-investors             | Top 5 by portfolio value       |
| POST /admin/seed                | Re-seed 100 portfolios         |

---

## How It Works (No Docker)

- Uses **moto** (Python library) to mock AWS DynamoDB, SQS, EventBridge in-memory
- Price simulation runs in a background thread every 5-10 seconds
- Risk engine detects breaches and generates AI insights automatically
- All data is in-memory — resets when backend restarts

## Risk Thresholds

- Allocation Drift > 5% from model allocation
- Single stock concentration > 20% of portfolio
- Daily portfolio drop > 3%

---

## Deploy to Real AWS (Optional)

```
cd infrastructure/cdk
pip install aws-cdk-lib constructs
aws configure
cdk bootstrap
cdk deploy
```
=======
# AI-Driven-Real-Time-Portfolio-Risk-Alert-System
>>>>>>> 21706cdd6cc54a2b6b15fb72d7c8337b88bca0ec
