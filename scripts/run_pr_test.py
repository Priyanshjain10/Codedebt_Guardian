import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.pr_generator import PRGenerator

def main():
    if not os.environ.get("GITHUB_TOKEN"):
        raise ValueError("GITHUB_TOKEN environment variable is not set. This is required to interact with the GitHub API.")
        
    pr_gen = PRGenerator()
    repo_url = "https://github.com/Priyanshjain10/codedebt-guardian"
    
    before_code = '''# TODO: fix this later
def bad_function(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p):
    try:
        pass
    except:
        password = os.environ.get("PASSWORD")  # TODO: Set in .env
        pass'''

    after_code = '''# TODO: fix this later
def bad_function(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p):
    try:
        pass
    except Exception as e:
        password = os.environ.get("PASSWORD")
        pass'''

    fix_proposal = {
        "fix_summary": "Fix bare except and hardcoded password",
        "before_code": before_code,
        "after_code": after_code,
        "steps": ["Replace except: with except Exception:", "Use os.environ for password"],
        "references": [],
        "estimated_time": "5 minutes"
    }

    issue = {
        "type": "bare_except_and_hardcoded_password",
        "description": "Found a bare except and a hardcoded password in the same function.",
        "location": "main.py:195",
        "severity": "HIGH",
        "score": 85,
        "effort_to_fix": "MINUTES",
        "impact": "Security vulnerability and poor error handling"
    }

    try:
        print("Submitting fix PR ...")
        pr = pr_gen.create_fix_pr(repo_url, fix_proposal, issue, base_branch="main")
        if pr:
            print(f"Success! PR URL: {pr.get('html_url', pr.get('url', 'Unknown URL'))}")
        else:
            print("Failed to create PR (returned None). Check branch logic and permissions.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
