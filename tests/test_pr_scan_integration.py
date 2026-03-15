"""
Tests for Phase 9: PR Scan Integration.
Validates that PR events create Scan records linked to Projects,
that the API returns the new fields, and that duplicates are prevented.
"""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from workers.pr_tasks import process_pr_event, MARKER


@pytest.fixture
def mock_requests():
    with patch("workers.pr_tasks.requests") as mock_req:
        yield mock_req


def _make_diff(content: str = "+try:\n+  pass\n+except:\n+  pass\n") -> str:
    return f"diff --git a/test.py b/test.py\n@@ -1,1 +1,4 @@\n{content}"


def test_pr_scan_record_created(mock_requests):
    """PR analysis should create a Scan record when a matching Project exists."""
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_project)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]

    diff_text = _make_diff("+try:\n+  pass\n+except:\n+  pass\n" * 3)

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "feature"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    with patch("database.SyncSessionLocal", return_value=mock_session):
        process_pr_event("testowner/testrepo", 42, "token")

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_pr_scan_linked_to_project(mock_requests):
    """The created Scan should have scan_type='pr' and the correct pr_number."""
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_project)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]

    diff_text = _make_diff()

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "dev"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    added_objects = []
    mock_session.add.side_effect = lambda obj: added_objects.append(obj)

    with patch("database.SyncSessionLocal", return_value=mock_session):
        process_pr_event("testowner/testrepo", 99, "token")

    assert len(added_objects) == 1
    scan = added_objects[0]
    assert scan.scan_type == "pr"
    assert scan.pr_number == 99
    assert scan.project_id == mock_project.id


def test_duplicate_pr_scan_updates_existing(mock_requests):
    """If a Scan for the same project+pr_number exists, it should be updated, not duplicated."""
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()

    existing_scan = MagicMock()
    existing_scan.id = uuid.uuid4()
    existing_scan.debt_score = 10

    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_project)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=existing_scan)),
    ]

    diff_text = _make_diff()

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "dev"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    with patch("database.SyncSessionLocal", return_value=mock_session):
        process_pr_event("testowner/testrepo", 42, "token")

    # Should NOT add a new object — just update the existing one
    mock_session.add.assert_not_called()
    mock_session.commit.assert_called_once()
    assert existing_scan.debt_score is not None
    assert existing_scan.status == "completed"


def test_pr_scan_not_persisted_without_project(mock_requests):
    """If no matching Project exists, the PR scan should still succeed (just not persisted)."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]

    diff_text = _make_diff()

    mock_requests.get.side_effect = [
        MagicMock(json=lambda: {"base": {"ref": "main"}}),
        MagicMock(text=diff_text),
        MagicMock(json=lambda: []),
    ]

    with patch("database.SyncSessionLocal", return_value=mock_session):
        process_pr_event("unknown/repo", 1, "token")

    mock_session.add.assert_not_called()
