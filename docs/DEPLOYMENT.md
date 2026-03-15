# Deployment Guide

## Docker Compose (Single Server)

Recommended for small teams and staging environments.

### Prerequisites
- Docker 24+ and Docker Compose v2
- 4GB+ RAM, 20GB disk
- Domain with DNS pointing to server

### Steps

```bash
# 1. Clone and configure
git clone https://github.com/codedebt/guardian.git && cd guardian
cp .env.example .env
# Edit .env: set SECRET_KEY, API keys, CORS_ORIGINS

# 2. Start all services
docker compose up -d

# 3. Run migrations
docker compose exec api alembic upgrade head

# 4. Verify
curl http://localhost:8000/health
# → {"status":"ok","database":"connected","redis":"connected"}
```

### Services
| Service | Port | URL |
|---|---|---|
| API Gateway | 8000 | http://localhost:8000 |
| Frontend | 3000 | http://localhost:3000 |
| Grafana | 3001 | http://localhost:3001 |
| PostgreSQL | 5432 | Internal |
| Redis | 6379 | Internal |

---

## Kubernetes

Recommended for production at scale.

### Prerequisites
- K8s cluster (EKS, GKE, AKS, or self-managed)
- `kubectl` and `helm` configured
- Ingress controller (nginx-ingress)
- cert-manager for TLS

### Steps

```bash
# 1. Create namespace
kubectl create namespace codedebt

# 2. Create secrets
kubectl create secret generic codedebt-secrets \
  --from-env-file=.env \
  -n codedebt

# 3. Apply manifests
kubectl apply -f k8s/ -n codedebt

# 4. Verify
kubectl get pods -n codedebt
```

### Scaling
- Workers auto-scale 2→10 via HPA based on CPU
- API runs 3 replicas with PodDisruptionBudget
- AI Gateway restricted to internal-only via NetworkPolicy

---

## Vercel + Render (Managed Cloud)

### Frontend → Vercel
```bash
cd frontend
npx vercel --prod
# Set env: NEXT_PUBLIC_API_URL=https://api.codedebt.dev
```

### Backend → Render
1. Create Web Service from repo
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables from `.env.example`

### Database → Neon
1. Create database at neon.tech
2. Enable pgvector extension
3. Set `DATABASE_URL` in Render env

### Redis → Upstash
1. Create Redis at upstash.com
2. Set `REDIS_URL` in Render env

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | JWT signing key (32+ chars) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `GOOGLE_API_KEY` | ⬚ | Gemini API key |
| `GROQ_API_KEY` | ⬚ | Groq API key |
| `GITHUB_TOKEN` | ⬚ | GitHub PAT for repo access |
| `STRIPE_SECRET_KEY` | ⬚ | Stripe billing |
| `CORS_ORIGINS` | ✅ | Allowed frontend origins |
