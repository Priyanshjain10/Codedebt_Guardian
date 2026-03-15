import pytest
from unittest.mock import patch, MagicMock
from tools.pr_generator import PRGenerator
import os

class TestPRGenerator:
    def setup_method(self):
        self.env_patcher = patch.dict('os.environ', {'GITHUB_TOKEN': 'fake-token', 'GOOGLE_API_KEY': 'fake-key'})
        self.user_patcher = patch('tools.pr_generator.PRGenerator._get_username', return_value='test-user')
        self.env_patcher.start()
        self.user_patcher.start()
        self.pr_gen = PRGenerator()

    def teardown_method(self):
        self.user_patcher.stop()
        self.env_patcher.stop()

    @patch('requests.Session.post')
    @patch('tools.pr_generator.PRGenerator._commit_file', return_value=True)
    @patch('tools.pr_generator.PRGenerator._get_file', return_value=("mock content", "mock-sha"))
    @patch('tools.pr_generator.PRGenerator._create_branch', return_value=True)
    @patch('tools.pr_generator.PRGenerator._get_branch_sha', return_value="mock-sha")
    def test_pr_logic(self, mock_get_branch_sha, mock_create_branch, mock_get_file, mock_commit_file, mock_post):
        """Verify PR logic (branch name format, draft status)"""
        repo_url = "https://github.com/mock/repo"
        fix_proposal = {"before_code": "a", "after_code": "b", "fix_summary": "Fix bugs"}
        issue = {"type": "bug", "location": "file.py:1"}

        mock_response = MagicMock()
        mock_response.json.return_value = {"number": 1, "title": "fix(Bug): [CodeDebt Guardian] Fix bugs", "html_url": "url", "state": "open"}
        mock_post.return_value = mock_response

        # Use an _apply_fix mock because we aren't testing string replacement here
        with patch.object(self.pr_gen, '_apply_fix', return_value="b"):
            self.pr_gen.create_fix_pr(repo_url, fix_proposal, issue)

        # Check Branch Name
        mock_create_branch.assert_called_once()
        branch_name = mock_create_branch.call_args[0][2]
        assert branch_name.startswith("codedebt/fix-bug-")

        # Check Draft Status
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert payload.get("draft") is True
        assert "fix(bug): [CodeDebt Guardian] Fix bugs" in payload.get("title")


class TestApplyFix:
    def setup_method(self):
        self.env_patcher = patch.dict('os.environ', {'GITHUB_TOKEN': 'fake-token', 'GOOGLE_API_KEY': 'fake-key'})
        self.user_patcher = patch('tools.pr_generator.PRGenerator._get_username', return_value='test-user')
        self.env_patcher.start()
        self.user_patcher.start()
        self.pr_gen = PRGenerator()

    def teardown_method(self):
        self.user_patcher.stop()
        self.env_patcher.stop()

    def test_string_replace_succeeds(self):
        file_content = "def foo():\n    return 1\n"
        fix_proposal = {
            "before_code": "return 1",
            "after_code": "return 2"
        }
        issue = {"type": "bug"}
        
        with patch.object(self.pr_gen, '_ai_apply_fix') as mock_ai:
            result = self.pr_gen._apply_fix(file_content, fix_proposal, issue)
            assert "return 2" in result
            mock_ai.assert_not_called()

    def test_unfixable_returns_original_content(self):
        file_content = "def foo():\n    return 1\n"
        # before_code not exactly in file
        fix_proposal = {
            "before_code": "return  1", # extra space
            "after_code": "return 2"
        }
        issue = {"type": "bug"}
        
        result = self.pr_gen._apply_fix(file_content, fix_proposal, issue)
        assert result == file_content

    def test_fix_unpinned_dependencies(self):
        file_content = "requests\npytest==8.0.0\nflask\n"
        fix_proposal = {}
        issue = {"type": "unpinned_dependencies"}
        result = self.pr_gen._apply_fix(file_content, fix_proposal, issue)
        assert "requests>=0.0.1" in result
        assert "pytest==8.0.0" in result
        assert "flask>=0.0.1" in result
