<div align="center">

# 🛡️ CodeDebt Guardian

### AI-Powered Technical Debt Detection & Remediation Platform

[![CI/CD](https://github.com/codedebt/guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/codedebt/guardian/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)

**Detect → Prioritize → Fix → Ship**

[Live Demo](https://codedebt-guardian.vercel.app) · [API Docs](docs/API.md) · [Architecture](docs/ARCHITECTURE.md) · [Deploy](docs/DEPLOYMENT.md)

</div>

---

## What is CodeDebt Guardian?

CodeDebt Guardian is an **AI-powered platform** that autonomously detects, prioritizes, and fixes technical debt in your codebase. It combines static analysis with multi-model AI (Gemini, Groq, GPT-4o) to find code smells, security vulnerabilities, and architectural issues — then generates fix PRs automatically.

### Key Features

| Feature | Description |
|---|---|
| 🤖 **AI Detection** | Multi-model pipeline scans for 500+ issue types using AST + AI |
| 📊 **Priority Ranking** | Issues scored by business impact, cost, and fix effort |
| 🔧 **Auto-Fix PRs** | AI generates code fixes and submits GitHub PRs |
| 🚪 **Debt Gate** | GitHub App blocks PRs that introduce new debt |
| 📈 **CTO Reports** | Executive summaries translating debt into dollar costs |
| ⚡ **Real-Time** | WebSocket streaming for live scan progress |
| 🏢 **Multi-Tenant** | Organizations, teams, projects with RBAC |
| 💳 **SaaS Billing** | Stripe integration with Free/Pro/Enterprise tiers |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Next.js Frontend                     │
│              (React 18 + Tailwind + Three.js)            │
└─────────────┬──────────────────────┬────────────────────┘
              │ REST API             │ WebSocket
┌─────────────▼──────────────────────▼────────────────────┐
│                   FastAPI Gateway                        │
│         (Auth · Rate Limiting · Request Routing)         │
└────┬──────┬──────┬──────┬──────┬──────┬─────────────────┘
     │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼
  Auth   Scan   Billing  API   Orgs  Webhook
  Svc    Orch    (Stripe) Keys  CRUD  (GitHub)
              │
              ▼
┌─────────────────────┐     ┌─────────────────────┐
│   Celery Workers    │────▶│    AI Gateway        │
│ (Analysis/Embed/PR) │     │ (Key Vault + Router) │
└─────────┬───────────┘     └──────┬──────────────┘
          │                        │
          ▼                        ▼
┌─────────────────┐     ┌──────────────────────┐
│  PostgreSQL 16  │     │   AI Providers       │
│   + pgvector    │     │ Gemini · Groq · GPT  │
└─────────────────┘     └──────────────────────┘
          │
    ┌─────▼─────┐
    │  Redis 7  │
    │ (Queue +  │
    │  Pub/Sub) │
    └───────────┘
```

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/codedebt/guardian.git
cd guardian

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker compose up -d

# API: http://localhost:8000
# Frontend: http://localhost:3000
# Grafana: http://localhost:3001
```

### Option 2: Local Development

```bash
# Backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Start PostgreSQL and Redis (via Docker)
docker compose up postgres redis -d

# Run migrations
alembic upgrade head

# Start API
uvicorn api.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A workers.celery_app worker --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Project Structure

```
codedebt-guardian/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point + auth endpoints
│   ├── auth.py            # JWT + API key authentication
│   ├── middleware.py       # Request ID, security headers, error handling
│   ├── websocket.py       # Real-time WebSocket server
│   ├── webhook.py         # GitHub Debt Gate webhook
│   └── routes/
│       ├── scans.py       # Scan CRUD + Celery dispatch
│       ├── organizations.py
│       ├── projects.py
│       ├── billing.py     # Stripe integration
│       └── api_keys.py
├── agents/                 # AI analysis pipeline
│   ├── orchestrator.py    # Pipeline coordinator
│   ├── debt_detection_agent.py
│   ├── priority_ranking_agent.py
│   └── fix_proposal_agent.py
├── services/
│   ├── ai_gateway.py      # Multi-model routing + key vault
│   └── embedding_pipeline.py  # Code chunking + pgvector
├── workers/
│   ├── celery_app.py      # Celery configuration
│   └── tasks.py           # Background scan/embed/PR tasks
├── models/
│   ├── schemas.py         # Pydantic API schemas
│   └── db_models.py       # SQLAlchemy ORM (15 tables)
├── tools/                  # Utility modules
├── frontend/               # Next.js 14 application
│   └── src/
│       ├── app/           # Pages (landing, dashboard, scan, settings)
│       ├── components/    # React components
│       └── lib/           # Store, API client
├── migrations/             # Alembic database migrations
├── k8s/                    # Kubernetes manifests
├── observability/          # Prometheus + Grafana configs
├── tests/                  # Test suite (120+ tests)
├── Dockerfile              # Multi-stage backend image
├── docker-compose.yml      # Full stack (8 services)
└── docs/                   # Documentation
```

---

## API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | No | Health check with dependency status |
| `/api/v1/auth/register` | POST | No | Register user + create org |
| `/api/v1/auth/login` | POST | No | Login → JWT tokens |
| `/api/v1/auth/me` | GET | Yes | Current user profile |
| `/api/v1/scans` | POST | Yes | Trigger new scan |
| `/api/v1/scans` | GET | Yes | List user's scans |
| `/api/v1/scans/{id}` | GET | Yes | Get scan results |
| `/api/v1/scans/{id}/fix/{i}` | POST | Yes | Create fix PR |
| `/api/v1/projects` | CRUD | Yes | Project management |
| `/api/v1/organizations` | GET | Yes | List user's orgs |
| `/api/v1/api-keys` | CRUD | Yes | API key management |
| `/api/v1/billing/usage` | GET | Yes | Usage stats |
| `/api/v1/billing/checkout` | POST | Yes | Stripe checkout |
| `/api/v1/ai/health` | GET | No | AI provider status |
| `/ws/scan/{id}` | WS | Opt | Real-time scan progress |

Full API documentation: [docs/API.md](docs/API.md)

---

## Testing

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html

# Run specific test modules
pytest tests/test_agents.py -v
pytest tests/test_api_v2.py -v
```

---

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment guides:
- **Docker Compose** — single-server deployment
- **Kubernetes** — scalable multi-node deployment
- **Vercel + Render** — managed cloud deployment
- **AWS** — ECS/EKS deployment

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, Framer Motion, Three.js |
| Backend | FastAPI, Python 3.12, Uvicorn, Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| Queue | Redis 7 + Celery 5 |
| AI | Gemini 2.0 Flash, Groq LLaMA 3.3, GPT-4o |
| Auth | JWT + bcrypt + GitHub OAuth |
| Billing | Stripe |
| Infra | Docker, Kubernetes, GitHub Actions |
| Observability | OpenTelemetry, Prometheus, Grafana |

---

## License

MIT © CodeDebt Guardian
