"""
Issue Tracker Integration — creates tickets in Jira or Linear from debt issues.
Closes the loop between detection and team workflow.
"""
import logging
import os
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JiraIntegration:
    """Creates Jira tickets from technical debt issues."""

    def __init__(self, base_url: str, email: str, api_token: str, project_key: str):
        self.base_url = base_url.rstrip("/")
        self.project_key = project_key
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    def create_tickets(self, issues: List[Dict], dry_run: bool = True) -> List[Dict]:
        results = []
        priority_map = {"CRITICAL": "Highest", "HIGH": "High",
                        "MEDIUM": "Medium", "LOW": "Low"}
        for issue in issues[:10]:
            sev = issue.get("severity", "MEDIUM")
            itype = issue.get("type", "debt").replace("_", " ").title()
            loc = issue.get("location", "unknown")
            desc = issue.get("description", "")
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": f"[TechDebt] {itype} in {loc.split(':')[0]}",
                    "description": {
                        "type": "doc", "version": 1,
                        "content": [{"type": "paragraph", "content": [
                            {"type": "text",
                             "text": f"{desc}\n\nLocation: {loc}\nSeverity: {sev}\n"
                                     f"Detected by CodeDebt Guardian."}
                        ]}]
                    },
                    "issuetype": {"name": "Task"},
                    "priority": {"name": priority_map.get(sev, "Medium")},
                    "labels": ["technical-debt", "codedebt-guardian"],
                }
            }
            if dry_run:
                results.append({"dry_run": True, "would_create": payload["fields"]["summary"]})
                continue
            try:
                r = requests.post(
                    f"{self.base_url}/rest/api/3/issue",
                    json=payload, auth=self.auth,
                    headers=self.headers, timeout=10
                )
                if r.status_code == 201:
                    data = r.json()
                    results.append({
                        "key": data.get("key"),
                        "url": f"{self.base_url}/browse/{data.get('key')}",
                        "summary": payload["fields"]["summary"],
                    })
                else:
                    logger.warning(f"Jira error {r.status_code}: {r.text[:200]}")
            except Exception as e:
                logger.error(f"Jira ticket creation failed: {e}")
        return results


class LinearIntegration:
    """Creates Linear issues from technical debt issues."""

    API_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: str, team_id: str):
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        self.team_id = team_id

    def create_issues(self, issues: List[Dict], dry_run: bool = True) -> List[Dict]:
        results = []
        priority_map = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
        for issue in issues[:10]:
            sev = issue.get("severity", "MEDIUM")
            itype = issue.get("type", "debt").replace("_", " ").title()
            loc = issue.get("location", "unknown")
            desc = issue.get("description", "")
            title = f"[TechDebt] {itype} in {loc.split(':')[0]}"
            body = (f"{desc}\n\n**Location:** `{loc}`\n"
                   f"**Severity:** {sev}\n"
                   f"*Detected by CodeDebt Guardian*")
            if dry_run:
                results.append({"dry_run": True, "would_create": title})
                continue
            query = """
            mutation CreateIssue($title: String!, $description: String!,
                                 $teamId: String!, $priority: Int!) {
              issueCreate(input: {
                title: $title
                description: $description
                teamId: $teamId
                priority: $priority
                labelNames: ["Technical Debt"]
              }) {
                success
                issue { id title url }
              }
            }"""
            try:
                r = requests.post(
                    self.API_URL,
                    json={"query": query, "variables": {
                        "title": title, "description": body,
                        "teamId": self.team_id,
                        "priority": priority_map.get(sev, 3)
                    }},
                    headers=self.headers, timeout=10
                )
                data = r.json()
                created = data.get("data", {}).get("issueCreate", {})
                if created.get("success"):
                    results.append({
                        "id": created["issue"]["id"],
                        "url": created["issue"]["url"],
                        "title": title,
                    })
            except Exception as e:
                logger.error(f"Linear issue creation failed: {e}")
        return results
