"""
Tests for Artifact Store Module
"""

import os
import json
import tempfile
import shutil
from pathlib import Path

import pytest

from modules.artifact_store import (
    ArtifactStore,
    FilesystemBackend,
    ArtifactStorageConfig,
    get_artifact_store,
)


@pytest.fixture
def temp_artifact_dir():
    """Create a temporary directory for artifact tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def filesystem_backend(temp_artifact_dir):
    """Create a filesystem backend with temp directory."""
    return FilesystemBackend(temp_artifact_dir)


@pytest.fixture
def artifact_store(temp_artifact_dir):
    """Create an artifact store with temp directory."""
    config = ArtifactStorageConfig(backend="filesystem", base_path=temp_artifact_dir)
    return ArtifactStore(config)


class TestFilesystemBackend:
    """Test FilesystemBackend."""
    
    def test_write_and_read_text(self, filesystem_backend):
        """Should write and read text content."""
        path = filesystem_backend.write("test/file.txt", "Hello, World!")
        content = filesystem_backend.read("test/file.txt")
        assert content == "Hello, World!"
    
    def test_write_and_read_binary(self, filesystem_backend):
        """Should write and read binary content."""
        # Use non-UTF8 bytes to ensure binary detection works
        data = b"\x80\x81\x82\x83\xff\xfe"
        path = filesystem_backend.write("test/file.bin", data, "application/octet-stream")
        content = filesystem_backend.read("test/file.bin")
        assert content == data
        assert isinstance(content, bytes)
    
    def test_read_nonexistent(self, filesystem_backend):
        """Reading nonexistent file should return None."""
        content = filesystem_backend.read("nonexistent/file.txt")
        assert content is None
    
    def test_exists(self, filesystem_backend):
        """Should check if file exists."""
        filesystem_backend.write("test.txt", "content")
        assert filesystem_backend.exists("test.txt") is True
        assert filesystem_backend.exists("other.txt") is False
    
    def test_delete_soft(self, filesystem_backend):
        """Soft delete should move to trash."""
        filesystem_backend.write("delete_me.txt", "content")
        assert filesystem_backend.exists("delete_me.txt") is True
        
        filesystem_backend.delete("delete_me.txt", soft=True)
        assert filesystem_backend.exists("delete_me.txt") is False
    
    def test_delete_hard(self, filesystem_backend):
        """Hard delete should permanently remove."""
        filesystem_backend.write("delete_me.txt", "content")
        filesystem_backend.delete("delete_me.txt", soft=False)
        assert filesystem_backend.exists("delete_me.txt") is False
    
    def test_delete_nonexistent(self, filesystem_backend):
        """Deleting nonexistent file should return False."""
        result = filesystem_backend.delete("nonexistent.txt")
        assert result is False
    
    def test_path_traversal_blocked(self, filesystem_backend):
        """Path traversal attempts should be blocked."""
        with pytest.raises(ValueError, match="Path traversal"):
            filesystem_backend.write("../outside.txt", "content")
    
    def test_path_traversal_blocked_absolute(self, filesystem_backend):
        """Absolute path outside base should be blocked."""
        with pytest.raises(ValueError, match="outside artifact store"):
            filesystem_backend.write("/etc/passwd", "content")
    
    def test_get_metadata(self, filesystem_backend):
        """Should get file metadata."""
        filesystem_backend.write("meta.txt", "Hello, World!")
        meta = filesystem_backend.get_metadata("meta.txt")
        
        assert meta["exists"] is True
        assert meta["size_bytes"] == 13
        assert meta["is_directory"] is False
        assert meta["checksum_sha256"] is not None
    
    def test_get_metadata_nonexistent(self, filesystem_backend):
        """Metadata for nonexistent file should indicate not exists."""
        meta = filesystem_backend.get_metadata("nonexistent.txt")
        assert meta["exists"] is False
    
    def test_list_artifacts(self, filesystem_backend):
        """Should list artifacts."""
        filesystem_backend.write("dir1/file1.txt", "content1")
        filesystem_backend.write("dir1/file2.txt", "content2")
        filesystem_backend.write("dir2/file3.txt", "content3")
        
        artifacts = filesystem_backend.list_artifacts("dir1")
        assert len(artifacts) == 2
        assert "dir1/file1.txt" in artifacts
        assert "dir1/file2.txt" in artifacts
    
    def test_list_artifacts_empty(self, filesystem_backend):
        """Listing nonexistent directory should return empty list."""
        artifacts = filesystem_backend.list_artifacts("nonexistent")
        assert artifacts == []


class TestArtifactStore:
    """Test ArtifactStore interface."""
    
    def test_write_and_read_artifact(self, artifact_store):
        """Should write and read artifact."""
        path = artifact_store.write_artifact(
            "crawl", "twin_123", "crawl_456",
            "manifest.json", '{"status": "ok"}'
        )
        
        content = artifact_store.read_artifact("crawl", "twin_123", "crawl_456", "manifest.json")
        assert content == '{"status": "ok"}'
    
    def test_write_and_read_json(self, artifact_store):
        """Should write and read JSON artifact."""
        data = {"status": "ok", "count": 42}
        artifact_store.write_json("research", "twin_123", "run_789", "data.json", data)
        
        result = artifact_store.read_json("research", "twin_123", "run_789", "data.json")
        assert result == data
    
    def test_read_json_nonexistent(self, artifact_store):
        """Reading nonexistent JSON should return None."""
        result = artifact_store.read_json("research", "twin_123", "run_789", "none.json")
        assert result is None
    
    def test_read_json_invalid(self, artifact_store):
        """Reading invalid JSON should return None."""
        artifact_store.write_artifact(
            "research", "twin_123", "run_789",
            "invalid.json", "not valid json"
        )
        result = artifact_store.read_json("research", "twin_123", "run_789", "invalid.json")
        assert result is None
    
    def test_artifact_exists(self, artifact_store):
        """Should check if artifact exists."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "test.txt", "content")
        
        assert artifact_store.artifact_exists("crawl", "twin_123", "crawl_456", "test.txt") is True
        assert artifact_store.artifact_exists("crawl", "twin_123", "crawl_456", "other.txt") is False
    
    def test_delete_artifact(self, artifact_store):
        """Should delete artifact."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "delete.txt", "content")
        
        result = artifact_store.delete_artifact("crawl", "twin_123", "crawl_456", "delete.txt")
        assert result is True
        assert artifact_store.artifact_exists("crawl", "twin_123", "crawl_456", "delete.txt") is False
    
    def test_list_artifacts(self, artifact_store):
        """Should list artifacts for entity."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "file1.txt", "content1")
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "file2.txt", "content2")
        
        artifacts = artifact_store.list_artifacts("crawl", "twin_123", "crawl_456")
        assert len(artifacts) == 2
        assert any("file1.txt" in a for a in artifacts)
        assert any("file2.txt" in a for a in artifacts)
    
    def test_get_metadata(self, artifact_store):
        """Should get artifact metadata."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "meta.txt", "Hello!")
        
        meta = artifact_store.get_artifact_metadata("crawl", "twin_123", "crawl_456", "meta.txt")
        assert meta["exists"] is True
        assert meta["size_bytes"] == 6
        assert meta["checksum_sha256"] is not None
    
    def test_read_by_path(self, artifact_store):
        """Should read by full path."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "test.txt", "content")
        
        content = artifact_store.read_by_path("crawl/twin_123/crawl_456/test.txt")
        assert content == "content"
    
    def test_delete_by_path(self, artifact_store):
        """Should delete by full path."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "test.txt", "content")
        
        result = artifact_store.delete_by_path("crawl/twin_123/crawl_456/test.txt")
        assert result is True
        assert artifact_store.artifact_exists("crawl", "twin_123", "crawl_456", "test.txt") is False


class TestArtifactStoreStructure:
    """Test artifact storage structure."""
    
    def test_crawl_artifact_path(self, artifact_store, temp_artifact_dir):
        """Crawl artifacts should be in correct path."""
        artifact_store.write_artifact("crawl", "twin_123", "crawl_456", "manifest.json", "{}")
        
        expected_path = Path(temp_artifact_dir) / "crawl" / "twin_123" / "crawl_456" / "manifest.json"
        assert expected_path.exists()
    
    def test_research_artifact_path(self, artifact_store, temp_artifact_dir):
        """Research artifacts should be in correct path."""
        artifact_store.write_artifact("research", "twin_123", "run_789", "synthesis.md", "# Report")
        
        expected_path = Path(temp_artifact_dir) / "research" / "twin_123" / "run_789" / "synthesis.md"
        assert expected_path.exists()


class TestTrashCleanup:
    """Test trash cleanup functionality."""
    
    def test_clean_trash(self, filesystem_backend):
        """Should clean old trash items."""
        # Write and delete something to create trash
        filesystem_backend.write("old.txt", "content")
        filesystem_backend.delete("old.txt", soft=True)
        
        # Clean trash with 0 days (should delete everything)
        deleted = filesystem_backend.clean_trash(max_age_days=0)
        assert deleted >= 1


class TestPathSecurity:
    """Test path security features."""
    
    def test_traversal_with_dotdot(self, filesystem_backend):
        """Path with .. should be rejected."""
        with pytest.raises(ValueError):
            filesystem_backend.write("foo/../bar.txt", "content")
    
    def test_traversal_with_encoded_dotdot(self, filesystem_backend):
        """Path with encoded .. should be rejected."""
        # Note: Pathlib normalizes this, so it may be caught differently
        with pytest.raises(ValueError):
            filesystem_backend.write("foo/..\x00/bar.txt", "content")
    
    def test_absolute_path_rejected(self, filesystem_backend):
        """Absolute path should be rejected."""
        with pytest.raises(ValueError):
            filesystem_backend.write("/absolute/path.txt", "content")


class TestGetArtifactStore:
    """Test get_artifact_store convenience function."""
    
    def test_get_store_with_config(self, temp_artifact_dir):
        """Should create store with provided config."""
        config = ArtifactStorageConfig(
            backend="filesystem",
            base_path=temp_artifact_dir
        )
        store = get_artifact_store(config)
        
        store.write_artifact("test", "t1", "e1", "f.txt", "content")
        assert store.artifact_exists("test", "t1", "e1", "f.txt") is True


class TestChecksumStability:
    """Test checksum consistency."""
    
    def test_same_content_same_checksum(self, filesystem_backend):
        """Same content should produce same checksum."""
        filesystem_backend.write("file1.txt", "Hello, World!")
        filesystem_backend.write("file2.txt", "Hello, World!")
        
        meta1 = filesystem_backend.get_metadata("file1.txt")
        meta2 = filesystem_backend.get_metadata("file2.txt")
        
        assert meta1["checksum_sha256"] == meta2["checksum_sha256"]
    
    def test_different_content_different_checksum(self, filesystem_backend):
        """Different content should produce different checksum."""
        filesystem_backend.write("file1.txt", "Hello, World!")
        filesystem_backend.write("file2.txt", "Goodbye, World!")
        
        meta1 = filesystem_backend.get_metadata("file1.txt")
        meta2 = filesystem_backend.get_metadata("file2.txt")
        
        assert meta1["checksum_sha256"] != meta2["checksum_sha256"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
