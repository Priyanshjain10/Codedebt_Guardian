import sys
import os

sys.path.insert(0, ".")
from agents.autopilot_agent import AutoPilotAgent, AutoPilotConfig

repo = os.environ.get("GITHUB_REPOSITORY", "")
repo_url = "https://github.com/" + repo
print("Analyzing: " + repo_url)

config = AutoPilotConfig(
    max_prs_per_day=3,
    draft_prs_only=True,
    dry_run=False,
    allowed_fix_types=["bare_except", "missing_docstring", "hardcoded_password"],
)
agent = AutoPilotAgent(config=config)
result = agent.run(repo_url)
print("Files analyzed: " + str(result.get("files_analyzed", 0)))
print("Issues found:   " + str(result.get("issues_found", 0)))
print("PRs created:    " + str(len(result.get("prs_created", []))))
for pr in result.get("prs_created", []):
    print("  PR: " + pr.get("url", ""))
