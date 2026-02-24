"""
Artifact Store Module

File-based artifact storage with S3-compatible interface for future migration.

Storage backends:
- filesystem: Local filesystem (default)
- s3: Amazon S3 / S3-compatible (future)

Artifact organization:
    {base_path}/
        {artifact_type}/
            {twin_id}/
                {entity_id}/
                    {filename}

Examples:
    artifacts/crawls/twin_123/crawl_456/manifest.json
    artifacts/crawls/twin_123/crawl_456/pages/page_789/normalized.md
    artifacts/research/twin_123/run_456/synthesis/certain_section.md
"""

import os
import shutil
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

from modules.deep_research_config import ArtifactStorageConfig, get_config


class ArtifactStoreBackend(ABC):
    """Abstract base class for artifact storage backends."""
    
    @abstractmethod
    def write(
        self,
        path: str,
        content: Union[str, bytes],
        content_type: str = "text/plain"
    ) -> str:
        """
        Write artifact and return full path/URI.
        
        Args:
            path: Relative path within artifact store
            content: Content to write
            content_type: MIME type of content
        
        Returns:
            Full path/URI to artifact
        """
        pass
    
    @abstractmethod
    def read(self, path: str) -> Optional[Union[str, bytes]]:
        """
        Read artifact content.
        
        Args:
            path: Path/URI to artifact
        
        Returns:
            Content or None if not found
        """
        pass
    
    @abstractmethod
    def delete(self, path: str, soft: bool = True) -> bool:
        """
        Delete artifact.
        
        Args:
            path: Path/URI to artifact
            soft: If True, move to trash instead of permanent delete
        
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if artifact exists."""
        pass
    
    @abstractmethod
    def get_metadata(self, path: str) -> Dict[str, Any]:
        """
        Get artifact metadata.
        
        Returns:
            Dict with size, modified_time, checksum, etc.
        """
        pass
    
    @abstractmethod
    def list_artifacts(self, prefix: str) -> List[str]:
        """List artifacts with given prefix."""
        pass


class FilesystemBackend(ArtifactStoreBackend):
    """
    Filesystem-based artifact storage.
    
    Directory structure:
        {base_path}/{relative_path}
    
    Trash folder:
        {base_path}/.trash/{timestamp}/{relative_path}
    """
    
    def __init__(self, base_path: str = "artifacts"):
        self.base_path = Path(base_path).resolve()
        self.trash_path = self.base_path / ".trash"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.trash_path.mkdir(parents=True, exist_ok=True)
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve relative path to absolute, ensuring it's within base_path."""
        # Normalize path and prevent directory traversal
        relative = Path(path)
        
        # Check for path traversal attempts
        if ".." in relative.parts:
            raise ValueError(f"Path traversal not allowed: {path}")
        
        absolute = self.base_path / relative
        
        # Ensure resolved path is within base_path (security check)
        try:
            absolute.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path outside artifact store: {path}")
        
        return absolute
    
    def write(
        self,
        path: str,
        content: Union[str, bytes],
        content_type: str = "text/plain"
    ) -> str:
        """Write artifact to filesystem."""
        absolute = self._resolve_path(path)
        
        # Create parent directories
        absolute.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        
        with open(absolute, mode, encoding=encoding) as f:
            f.write(content)
        
        return str(absolute.relative_to(self.base_path.parent))
    
    def read(self, path: str) -> Optional[Union[str, bytes]]:
        """Read artifact from filesystem."""
        try:
            absolute = self._resolve_path(path)
        except ValueError:
            return None
        
        if not absolute.exists():
            return None
        
        # Check if file is binary by reading first chunk
        with open(absolute, "rb") as f:
            chunk = f.read(8192)
            
        # Try to decode as UTF-8
        try:
            chunk.decode('utf-8')
            # If successful, read as text
            with open(absolute, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Binary file, return bytes
            with open(absolute, "rb") as f:
                return f.read()
    
    def delete(self, path: str, soft: bool = True) -> bool:
        """Delete artifact (soft or hard delete)."""
        try:
            absolute = self._resolve_path(path)
        except ValueError:
            return False
        
        if not absolute.exists():
            return False
        
        if soft:
            # Move to trash
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            trash_dir = self.trash_path / timestamp / Path(path).parent
            trash_dir.mkdir(parents=True, exist_ok=True)
            trash_target = trash_dir / Path(path).name
            
            # Handle name collisions in trash
            counter = 0
            original_target = trash_target
            while trash_target.exists():
                counter += 1
                trash_target = original_target.parent / f"{original_target.stem}_{counter}{original_target.suffix}"
            
            shutil.move(str(absolute), str(trash_target))
        else:
            # Permanent delete
            if absolute.is_dir():
                shutil.rmtree(absolute)
            else:
                absolute.unlink()
        
        return True
    
    def exists(self, path: str) -> bool:
        """Check if artifact exists."""
        try:
            absolute = self._resolve_path(path)
            return absolute.exists()
        except ValueError:
            return False
    
    def get_metadata(self, path: str) -> Dict[str, Any]:
        """Get artifact metadata."""
        try:
            absolute = self._resolve_path(path)
        except ValueError as e:
            return {"error": str(e)}
        
        if not absolute.exists():
            return {"exists": False}
        
        stat = absolute.stat()
        
        # Compute checksum
        checksum = None
        if absolute.is_file():
            sha256 = hashlib.sha256()
            try:
                with open(absolute, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
                checksum = sha256.hexdigest()
            except Exception:
                pass
        
        return {
            "exists": True,
            "path": path,
            "absolute_path": str(absolute),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_directory": absolute.is_dir(),
            "checksum_sha256": checksum,
        }
    
    def list_artifacts(self, prefix: str = "") -> List[str]:
        """List artifacts with given prefix."""
        try:
            base = self._resolve_path(prefix) if prefix else self.base_path
        except ValueError:
            return []
        
        if not base.exists():
            return []
        
        artifacts = []
        if base.is_dir():
            for item in base.rglob("*"):
                if item.is_file():
                    try:
                        rel_path = item.relative_to(self.base_path)
                        artifacts.append(str(rel_path))
                    except ValueError:
                        pass
        else:
            try:
                rel_path = base.relative_to(self.base_path)
                artifacts.append(str(rel_path))
            except ValueError:
                pass
        
        artifacts = sorted(artifacts)
        # Normalize path separators to forward slashes for cross-platform consistency
        artifacts = [a.replace('\\', '/') for a in artifacts]
        return artifacts
    
    def clean_trash(self, max_age_days: int = 7) -> int:
        """
        Clean old items from trash.
        
        Args:
            max_age_days: Delete items older than this
        
        Returns:
            Number of items deleted
        """
        if not self.trash_path.exists():
            return 0
        
        deleted = 0
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 24 * 60 * 60)
        
        for item in self.trash_path.iterdir():
            if item.is_dir():
                try:
                    # Parse timestamp from folder name
                    stat = item.stat()
                    if stat.st_ctime < cutoff:
                        shutil.rmtree(item)
                        deleted += 1
                except Exception:
                    pass
        
        return deleted


class S3Backend(ArtifactStoreBackend):
    """
    S3-compatible artifact storage (future implementation).
    
    Interface is defined for future migration but not implemented yet.
    """
    
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = "artifacts"
    ):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix
        raise NotImplementedError("S3 backend not yet implemented")
    
    def write(self, path: str, content: Union[str, bytes], content_type: str = "text/plain") -> str:
        raise NotImplementedError()
    
    def read(self, path: str) -> Optional[Union[str, bytes]]:
        raise NotImplementedError()
    
    def delete(self, path: str, soft: bool = True) -> bool:
        raise NotImplementedError()
    
    def exists(self, path: str) -> bool:
        raise NotImplementedError()
    
    def get_metadata(self, path: str) -> Dict[str, Any]:
        raise NotImplementedError()
    
    def list_artifacts(self, prefix: str) -> List[str]:
        raise NotImplementedError()


class ArtifactStore:
    """
    Main artifact store interface.
    
    Uses backend pattern for swappable storage:
    - FilesystemBackend (default)
    - S3Backend (future)
    
    Artifact path format:
        {type}/{twin_id}/{entity_id}/{filename}
    
    Examples:
        crawl/twin_123/crawl_456/manifest.json
        research/twin_123/run_456/claims/all_claims.json
    """
    
    def __init__(self, config: Optional[ArtifactStorageConfig] = None):
        self.config = config or get_config().artifacts
        self._backend = self._create_backend()
    
    def _create_backend(self) -> ArtifactStoreBackend:
        """Create storage backend based on configuration."""
        if self.config.backend == "filesystem":
            return FilesystemBackend(self.config.base_path)
        elif self.config.backend == "s3":
            return S3Backend(
                bucket=self.config.s3_bucket,
                region=self.config.s3_region,
                prefix=self.config.s3_prefix
            )
        else:
            raise ValueError(f"Unknown storage backend: {self.config.backend}")
    
    def _build_path(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str
    ) -> str:
        """Build standardized artifact path."""
        return f"{artifact_type}/{twin_id}/{entity_id}/{filename}"
    
    def write_artifact(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str,
        content: Union[str, bytes],
        content_type: str = "text/plain"
    ) -> str:
        """
        Write artifact to storage.
        
        Args:
            artifact_type: Type of artifact (crawl, research, etc.)
            twin_id: Twin ID
            entity_id: Entity ID (crawl_id, run_id, etc.)
            filename: Filename
            content: Content to write
            content_type: MIME type
        
        Returns:
            Path to stored artifact
        """
        path = self._build_path(artifact_type, twin_id, entity_id, filename)
        return self._backend.write(path, content, content_type)
    
    def read_artifact(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str
    ) -> Optional[Union[str, bytes]]:
        """Read artifact from storage."""
        path = self._build_path(artifact_type, twin_id, entity_id, filename)
        return self._backend.read(path)
    
    def read_by_path(self, path: str) -> Optional[Union[str, bytes]]:
        """Read artifact by full path."""
        return self._backend.read(path)
    
    def delete_artifact(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str,
        soft: bool = True
    ) -> bool:
        """Delete artifact."""
        path = self._build_path(artifact_type, twin_id, entity_id, filename)
        return self._backend.delete(path, soft)
    
    def delete_by_path(self, path: str, soft: bool = True) -> bool:
        """Delete artifact by full path."""
        return self._backend.delete(path, soft)
    
    def artifact_exists(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str
    ) -> bool:
        """Check if artifact exists."""
        path = self._build_path(artifact_type, twin_id, entity_id, filename)
        return self._backend.exists(path)
    
    def get_artifact_metadata(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str
    ) -> Dict[str, Any]:
        """Get artifact metadata."""
        path = self._build_path(artifact_type, twin_id, entity_id, filename)
        return self._backend.get_metadata(path)
    
    def list_artifacts(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str
    ) -> List[str]:
        """List all artifacts for an entity."""
        prefix = f"{artifact_type}/{twin_id}/{entity_id}/"
        return self._backend.list_artifacts(prefix)
    
    def write_json(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str,
        data: Any
    ) -> str:
        """Write JSON artifact."""
        content = json.dumps(data, indent=2, default=str)
        return self.write_artifact(
            artifact_type, twin_id, entity_id, filename,
            content, "application/json"
        )
    
    def read_json(
        self,
        artifact_type: str,
        twin_id: str,
        entity_id: str,
        filename: str
    ) -> Optional[Any]:
        """Read and parse JSON artifact."""
        content = self.read_artifact(artifact_type, twin_id, entity_id, filename)
        if content is None:
            return None
        
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    
    def clean_trash(self, max_age_days: int = 7) -> int:
        """Clean old items from trash (filesystem backend only)."""
        if isinstance(self._backend, FilesystemBackend):
            return self._backend.clean_trash(max_age_days)
        return 0


# Convenience functions
def get_artifact_store(config: Optional[ArtifactStorageConfig] = None) -> ArtifactStore:
    """Get configured artifact store instance."""
    return ArtifactStore(config)
