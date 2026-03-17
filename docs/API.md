# API Reference

Base URL: `http://localhost:8000` (dev) or `https://api.codedebt.dev` (prod)

## Authentication

All endpoints marked "Auth: Yes" require a header:
```
Authorization: Bearer <jwt_token>
```
Or an API key:
```
Authorization: Bearer cdg_live_xxxxx
```

---

## Auth Endpoints

### POST /api/v1/auth/register
Create a new user with a default organization.

**Request:**
```json
{
  "email": "dev@example.com",
  "password": "securepassword123",
  "name": "Jane Dev"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### POST /api/v1/auth/login
Login with email and password.

**Request:**
```json
{
  "email": "dev@example.com",
  "password": "securepassword123"
}
```

### GET /api/v1/auth/me
Get current user profile. **Auth: Yes**

**Response:**
```json
{
  "id": "uuid",
  "email": "dev@example.com",
  "name": "Jane Dev",
  "avatar_url": null,
  "created_at": "2026-03-11T00:00:00Z"
}
```

---

## Scans

### POST /api/v1/scans
Trigger a new code analysis scan. Returns immediately; analysis runs in background. **Auth: Yes**

**Request:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "branch": "main"
}
```

**Response (202):**
```json
{
  "scan_id": "uuid",
  "status": "queued",
  "ws_url": "/ws/scan/{scan_id}",
  "message": "Scan queued. Connect to WebSocket for live progress."
}
```

### GET /api/v1/scans
List scans. **Auth: Yes**

Query params: `limit`, `offset`, `status`

### GET /api/v1/scans/{id}
Get full scan results. **Auth: Optional**

**Response:**
```json
{
  "id": "uuid",
  "status": "completed",
  "summary": {
    "total_issues": 23,
    "critical": 2,
    "high": 5,
    "grade": "B"
  },
  "ranked_issues": [...],
  "fix_proposals": [...],
  "tdr": {...},
  "duration_seconds": 45.2
}
```

### POST /api/v1/scans/{id}/fix/{index}
Create a GitHub PR for a fix proposal. **Auth: Yes**

---

## Projects

### POST /api/v1/projects
Create a project linked to a GitHub repo. **Auth: Yes**

### GET /api/v1/projects
List projects. **Auth: Yes**

### DELETE /api/v1/projects/{id}
Delete a project. **Auth: Yes**

---

## API Keys

### POST /api/v1/api-keys
Generate a new API key. Key shown only once. **Auth: Yes**

**Response:**
```json
{
  "id": "uuid",
  "key": "cdg_live_xxxxxxxxxxxxxx",
  "prefix": "cdg_live_xxxxxx",
  "label": "production"
}
```

### GET /api/v1/api-keys
List active keys (prefix only). **Auth: Yes**

### DELETE /api/v1/api-keys/{id}
Revoke an API key. **Auth: Yes**

---

## Billing

### GET /api/v1/billing/usage
Get current plan and usage. **Auth: Yes**

### POST /api/v1/billing/checkout
Create Stripe checkout session. **Auth: Yes**

---

## WebSocket

### /ws/scan/{scan_id}?token={jwt}

Real-time scan progress. Events:
```json
{"type": "scan.progress", "message": "Scanning files...", "percent": 30}
{"type": "scan.complete", "data": {...}}
{"type": "scan.error", "message": "Analysis failed"}
{"type": "heartbeat"}
```

---

## Health

### GET /health
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "ai_providers": {"groq": true, "gemini": true, "openai": false}
}
```

---

## Error Format
All errors return:
```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "request_id": "uuid"
}
```

| Status | Meaning |
|---|---|
| 400 | Bad request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not found |
| 409 | Conflict |
| 429 | Rate limited |
| 500 | Internal error |
