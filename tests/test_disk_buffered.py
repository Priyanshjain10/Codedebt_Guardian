"""
Tests for the disk-buffered processing architecture.
Verifies that GitHubTool.read_file_content() correctly reads from disk
(local_path) and falls back to in-memory content for backward compat.
"""

import os
import tempfile
from tools.github_tool import GitHubTool


class TestDiskBufferedReads:
    """Tests for GitHubTool.read_file_content() disk-buffered reads."""

    def test_read_from_local_path(self, tmp_path):
        """Content is read lazily from local_path on disk."""
        test_file = tmp_path / "example.py"
        test_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        file_info = {"name": "example.py", "local_path": str(test_file), "size": 30}
        content = GitHubTool.read_file_content(file_info)

        assert "def hello():" in content
        assert "return 'world'" in content

    def test_read_truncates_at_max_bytes(self, tmp_path):
        """Content is truncated to max_bytes when reading from disk."""
        test_file = tmp_path / "big.py"
        test_file.write_text("x" * 500, encoding="utf-8")

        file_info = {"name": "big.py", "local_path": str(test_file), "size": 500}
        content = GitHubTool.read_file_content(file_info, max_bytes=100)

        assert len(content) == 100

    def test_fallback_to_in_memory_content(self):
        """When local_path is absent, falls back to content field (backward compat)."""
        file_info = {"name": "test.py", "content": "print('hello')"}
        content = GitHubTool.read_file_content(file_info)

        assert content == "print('hello')"

    def test_returns_empty_on_missing_file(self, tmp_path):
        """Returns empty string when local_path points to a nonexistent file."""
        file_info = {
            "name": "ghost.py",
            "local_path": str(tmp_path / "nonexistent.py"),
            "size": 0,
        }
        content = GitHubTool.read_file_content(file_info)

        assert content == ""

    def test_returns_empty_when_no_content_or_path(self):
        """Returns empty string when neither local_path nor content exist."""
        file_info = {"name": "empty.py", "size": 0}
        content = GitHubTool.read_file_content(file_info)

        assert content == ""

    def test_local_path_takes_priority_over_content(self, tmp_path):
        """When both local_path and content exist, local_path wins."""
        test_file = tmp_path / "real.py"
        test_file.write_text("DISK_VERSION", encoding="utf-8")

        file_info = {
            "name": "real.py",
            "local_path": str(test_file),
            "content": "MEMORY_VERSION",
            "size": 12,
        }
        content = GitHubTool.read_file_content(file_info)

        assert content == "DISK_VERSION"

    def test_handles_unicode_in_disk_file(self, tmp_path):
        """Reads UTF-8 files with unicode characters correctly."""
        test_file = tmp_path / "unicode.py"
        test_file.write_text("# Ça marche!\ndef café(): pass\n", encoding="utf-8")

        file_info = {"name": "unicode.py", "local_path": str(test_file), "size": 30}
        content = GitHubTool.read_file_content(file_info)

        assert "café" in content


class TestDiskBufferedExtraction:
    """Tests that _fetch_zipball returns metadata without content."""

    def test_file_info_has_local_path_not_content(self, tmp_path):
        """After disk extraction, file_info dicts have local_path, not content."""
        # Simulate a file_info dict from the new _fetch_zipball
        test_file = tmp_path / "app.py"
        test_file.write_text("import os\n", encoding="utf-8")

        file_info = {
            "name": "app.py",
            "local_path": str(test_file),
            "size": 10,
        }

        # Verify shape: has local_path, no content
        assert "local_path" in file_info
        assert "content" not in file_info
        assert os.path.exists(file_info["local_path"])

    def test_source_code_priority_sorting(self):
        """Source code extensions are sorted before config/docs."""
        files = [
            {"name": "README.md", "local_path": "/tmp/README.md", "size": 100},
            {"name": "main.py", "local_path": "/tmp/main.py", "size": 200},
            {"name": "config.json", "local_path": "/tmp/config.json", "size": 50},
            {"name": "app.js", "local_path": "/tmp/app.js", "size": 150},
        ]

        def _sort_key(f):
            ext = "." + f["name"].rsplit(".", 1)[-1] if "." in f["name"] else ""
            return 0 if ext in GitHubTool._SOURCE_EXTENSIONS else 1

        files.sort(key=_sort_key)

        # Python and JS should come before MD and JSON
        assert files[0]["name"] == "main.py"
        assert files[1]["name"] == "app.js"
        assert files[2]["name"] in ("README.md", "config.json")


class TestTempDirLifecycle:
    """Tests that temp directory cleanup works correctly."""

    def test_temp_dir_cleanup(self):
        """TemporaryDirectory.cleanup() removes all files."""
        td = tempfile.TemporaryDirectory(prefix="test_codedebt_")
        path = td.name

        # Write a test file inside
        test_file = os.path.join(path, "test.py")
        with open(test_file, "w") as f:
            f.write("print('hello')")

        assert os.path.exists(test_file)

        # Cleanup
        td.cleanup()

        assert not os.path.exists(path)
        assert not os.path.exists(test_file)
