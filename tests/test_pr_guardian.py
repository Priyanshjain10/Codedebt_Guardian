import pytest
from unittest.mock import patch, MagicMock
from workers.pr_tasks import process_pr_event, MARKER


@pytest.fixture
def mock_requests():
    with patch("workers.pr_tasks.requests") as mock_req:
        yield mock_req


@pytest.fixture
def mock_pr_generator():
    with patch("tools.pr_generator.PRGenerator") as mock_pr_gen_class:
        mock_instance = MagicMock()
        mock_pr_gen_class.return_value = mock_instance
        yield mock_instance


def test_clean_pr(mock_requests, mock_pr_generator):
    """Test a PR with no technical debt added."""
    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),  # PR check
        MagicMock(
            text="diff --git a/test.py b/test.py\n@@ -1,1 +1,2 @@\n+print('hello')\n"
        ),  # diff
        MagicMock(json=lambda: []),  # comments get
    ]

    process_pr_event("owner/repo", 1, "token")

    # Should not post comments (score <= 25)
    mock_requests.post.assert_not_called()
    mock_pr_generator.create_fix_pr.assert_not_called()


def test_high_debt_pr(mock_requests, mock_pr_generator):
    """Test a PR with high debt (score > 60)."""
    # Create diff with multiple hardcoded credentials to trigger high score
    # 2 credentials (CRITICAL) = 2 * 40 = 80 score
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,4 @@\n"
    diff_text += "+password = 'super_secret1'\n"
    diff_text += "+api_key = 'super_secret2'\n"

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    process_pr_event("owner/repo", 2, "token")

    # Should post a comment because score is high
    mock_requests.post.assert_called_once()
    args, kwargs = mock_requests.post.call_args
    assert "CodeDebt Guardian" in kwargs["json"]["body"]
    assert str(MARKER) in kwargs["json"]["body"]

    # Should not auto-fix since base is main
    mock_pr_generator.create_fix_pr.assert_not_called()


def test_moderate_debt_pr(mock_requests, mock_pr_generator):
    """Test a PR with moderate debt (score 26-60)."""
    # 1 bare except = 63.75 cost, 1 medium severity = score around 10
    # Wait, the score rules are: critical*40 + high*20 + medium*10 + low*5
    # So 3 bare excepts = 3 medium = score 30
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,6 @@\n"
    diff_text += "+try:\n+  pass\n+except:\n+  pass\n" * 3

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    process_pr_event("owner/repo", 3, "token")

    # Score should be 30, which posts a comment
    mock_requests.post.assert_called_once()
    args, kwargs = mock_requests.post.call_args
    assert "Review recommended before merge." in kwargs["json"]["body"]


def test_comment_update_instead_of_duplicate(mock_requests, mock_pr_generator):
    """Ensure we update the existing comment if it has the MARKET."""
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,6 @@\n"
    diff_text += "+try:\n+  pass\n+except:\n+  pass\n" * 3

    existing_comment = {
        "id": 999,
        "body": f"Old comment\\n\\n{MARKER}",
    }

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),
        MagicMock(text=diff_text),
        MagicMock(
            json=lambda: [existing_comment, {"id": 1000, "body": "regular comment"}]
        ),
    ]

    process_pr_event("owner/repo", 4, "token")

    # Should NOT post a new comment
    mock_requests.post.assert_not_called()

    # Should PATCH the existing comment
    mock_requests.patch.assert_called_once()
    args, kwargs = mock_requests.patch.call_args
    assert "issues/comments/999" in args[0]
    assert "Review recommended before merge." in kwargs["json"]["body"]
    assert str(MARKER) in kwargs["json"]["body"]


def test_auto_fix_triggered(mock_requests, mock_pr_generator):
    """Test auto-fix is triggered for safe issues on non-main branch."""
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,4 @@\n"
    diff_text += "+try:\n+  pass\n+except:\n+  pass"

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "feature"}}),  # NOT main
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    process_pr_event("owner/repo", 5, "token")

    # Score = 1 medium = 10 -> No comment
    mock_requests.post.assert_not_called()

    # Auto fix SHOULD trigger
    mock_pr_generator.create_fix_pr.assert_called_once()
    kwargs = mock_pr_generator.create_fix_pr.call_args[1]
    assert kwargs["base_branch"] == "feature"
    assert "bare_except" in kwargs["issue"]["type"]


def test_auto_fix_blocked_by_branch(mock_requests, mock_pr_generator):
    """Test auto-fix is blocked if base branch is main."""
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,4 @@\n"
    diff_text += "+try:\n+  pass\n+except:\n+  pass"

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),  # IS main
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    process_pr_event("owner/repo", 6, "token")

    # Auto fix SHOULD NOT trigger
    mock_pr_generator.create_fix_pr.assert_not_called()


def test_auto_fix_blocked_by_diff_size(mock_requests, mock_pr_generator):
    """Test auto-fix is blocked if the Diff size is >= 50."""
    diff_text = "diff --git a/test.py b/test.py\n@@ -1,1 +1,52 @@\n"
    diff_text += "+try:\n+  pass\n+except:\n+  pass\n"
    diff_text += "+print('x')\n" * 50  # pad diff size

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "feature"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    process_pr_event("owner/repo", 7, "token")

    # Auto fix SHOULD NOT trigger because total added lines > 50
    mock_pr_generator.create_fix_pr.assert_not_called()
