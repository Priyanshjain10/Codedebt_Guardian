# CodeDebt Guardian GitHub Action

Automatically detects technical debt in your codebase on every PR and push.
Posts a summary to GitHub Actions and optionally fails the workflow on critical issues.

## Quick Start

```yaml
# .github/workflows/debt-scan.yml
name: CodeDebt Scan

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 9 * * 1'  # Every Monday 9am

jobs:
  debt-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Scan for technical debt
        uses: your-org/codedebt-guardian@v1
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          groq-api-key: ${{ secrets.GROQ_API_KEY }}
          fail-on-critical: true
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `repo-token` | ✅ | — | GitHub token for repo access |
| `groq-api-key` | ❌ | `""` | Groq API key for AI analysis (free tier: 14,400 req/day) |
| `fail-on-critical` | ❌ | `false` | Fail workflow if CRITICAL issues found |
| `min-score` | ❌ | `0` | Minimum health score (0–100) |
| `max-debt-dollars` | ❌ | `500` | Max debt cost in USD before failing |

## Outputs

| Output | Description |
|--------|-------------|
| `debt-score` | TDR health grade (A/B/C/D/F) |
| `critical-count` | Number of CRITICAL issues |
| `high-count` | Number of HIGH issues |

## Using outputs in subsequent steps

```yaml
- name: Scan for technical debt
  id: debt
  uses: your-org/codedebt-guardian@v1
  with:
    repo-token: ${{ secrets.GITHUB_TOKEN }}

- name: Comment grade on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `Health grade: **${{ steps.debt.outputs.debt-score }}** | Critical: ${{ steps.debt.outputs.critical-count }}`
      })
```

## Get your free Groq API key

1. Sign up at [console.groq.com](https://console.groq.com)
2. Create an API key
3. Add it as `GROQ_API_KEY` in your repo secrets

The free tier gives you 14,400 requests/day on Llama 3.3 70B — more than enough for most repos.

## Run Ollama locally (zero API cost)

If you self-host the action runner, you can use Ollama for zero-cost AI analysis:

```bash
# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull qwen2.5-coder:7b
```

The action auto-detects Ollama at `http://localhost:11434` and uses it as the primary provider.
