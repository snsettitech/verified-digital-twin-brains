"""
Crawl Ingestion Bridge Module (Phase 2.1 + 3.5)

Bridges crawl_pages to existing source ingestion pipeline.
Converts crawl artifacts into source records with proper chunking and indexing.

Phase 3.5 Addition: Confirmation-gated ingestion for onboarding-driven research flow.

Key Features:
- Load content from artifacts (not DB)
- Skip unchanged pages (idempotent ingestion)
- Preserve twin isolation
- Integrate with existing chunking/indexing pipeline
- Phase 3.5: Confirmation-gated mode for research runs
"""

import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime
from pathlib import PurePosixPath

from modules.crawl_repository import CrawlRepository
from modules.artifact_store import get_artifact_store
from modules.observability import supabase
from modules.chunking_utils import chunk_with_source_policy
from modules.embeddings import get_embedding
from modules.pinecone_adapter import PineconeIndexAdapter, DEFAULT_METADATA_FIELDS
from modules.clients import get_pinecone_index
from modules.chunk_version_manager import ChunkVersionManager

logger = logging.getLogger(__name__)

# Phase 3.5: Import for confirmation lookups
from modules.source_confirmation import SourceConfirmationManager


class CrawlIngestionBridge:
    """
    Bridges crawl artifacts to source ingestion pipeline.
    
    Responsibilities:
    1. Load content from artifact store
    2. Skip unchanged pages (idempotency)
    3. Create source records
    4. Trigger chunking and indexing
    5. Track ingestion statistics
    6. Phase 3.5: Confirmation-gated ingestion for research runs
    """
    
    def __init__(self):
        self.repository = CrawlRepository()
        self.artifact_store = get_artifact_store()
        self.version_manager = ChunkVersionManager()
        self.confirmation_manager = SourceConfirmationManager()

    @staticmethod
    def _resolve_artifact_scope(
        page: Dict[str, Any],
        twin_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Resolve the artifact scope for a crawl page.

        Historical crawl_pages rows do not include twin_id, so callers must be
        able to supply it from the crawl/research run context. As a fallback,
        derive it from normalized_artifact_path when available.
        """
        resolved_twin_id = str(twin_id or page.get("twin_id") or "").strip()
        resolved_crawl_id = str(page.get("crawl_id") or "").strip()

        if resolved_twin_id and resolved_crawl_id:
            return resolved_twin_id, resolved_crawl_id

        normalized_path = str(page.get("normalized_artifact_path") or "").strip()
        if not normalized_path:
            return resolved_twin_id, resolved_crawl_id

        parts = [part for part in PurePosixPath(normalized_path).parts if part and part != "."]
        if not parts:
            return resolved_twin_id, resolved_crawl_id

        # Stored artifact paths may be either:
        # - crawl/{twin_id}/{crawl_id}/pages/{page_id}/normalized.md
        # - artifacts/crawl/{twin_id}/{crawl_id}/pages/{page_id}/normalized.md
        if parts[0] == "artifacts":
            parts = parts[1:]

        if len(parts) >= 3 and parts[0] == "crawl":
            if not resolved_twin_id:
                resolved_twin_id = parts[1]
            if not resolved_crawl_id:
                resolved_crawl_id = parts[2]

        return resolved_twin_id, resolved_crawl_id
    
    def should_skip_ingestion(
        self,
        page: Dict[str, Any],
        twin_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if a page should be skipped during ingestion.
        
        Skip conditions:
        - Page classification is UNCHANGED (content hasn't changed)
        - Page status is failed/blocked/error
        - No normalized artifact exists
        
        Args:
            page: Crawl page record
            
        Returns:
            Tuple of (should_skip, reason)
        """
        # Some historical crawl_pages rows store nullable text fields.
        # Normalize defensively so ingestion doesn't crash on None values.
        status = str(page.get("status") or "").lower()
        classification = str(page.get("classification") or "").lower()
        normalized_path = page.get("normalized_artifact_path")
        
        # Skip unchanged pages - they reference prior artifacts
        if classification == "unchanged":
            return True, "unchanged_content"
        
        # Skip failed/blocked pages
        if status in ("failed", "blocked", "error"):
            return True, f"page_status_{status}"
        
        # Skip pages without normalized content
        if not normalized_path:
            return True, "no_normalized_artifact"

        artifact_twin_id, artifact_crawl_id = self._resolve_artifact_scope(page, twin_id)
        if not artifact_twin_id or not artifact_crawl_id:
            return True, "artifact_scope_unknown"
        
        # Check if artifact exists
        if not self.artifact_store.artifact_exists(
            artifact_type="crawl",
            twin_id=artifact_twin_id,
            entity_id=artifact_crawl_id,
            filename=f"pages/{page.get('id')}/normalized.md"
        ):
            return True, "artifact_not_found"
        
        return False, ""
    
    def should_skip_ingestion_confirmation_gate(
        self,
        page: Dict[str, Any],
        confirmed_page_ids: Set[str]
    ) -> Tuple[bool, str]:
        """
        Phase 3.5: Check confirmation gate for gated ingestion mode.
        
        Args:
            page: Crawl page record
            confirmed_page_ids: Set of page IDs that are confirmed/auto_confirmed
            
        Returns:
            Tuple of (should_skip, reason)
        """
        page_id = page.get("id", "")
        
        if page_id not in confirmed_page_ids:
            # Check if there's a specific rejection reason
            return True, "not_confirmed"
        
        return False, ""
    
    def load_page_content(self, page: Dict[str, Any], twin_id: str) -> Optional[str]:
        """
        Load normalized content from artifact store.
        
        Args:
            page: Crawl page record
            twin_id: Twin ID for artifact path
            
        Returns:
            Content string or None if not found
        """
        crawl_id = page.get("crawl_id", "")
        page_id = page.get("id", "")
        
        content = self.artifact_store.read_artifact(
            artifact_type="crawl",
            twin_id=twin_id,
            entity_id=crawl_id,
            filename=f"pages/{page_id}/normalized.md"
        )
        
        if content is None:
            logger.warning(f"Content not found for page {page_id}")
            return None
        
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        
        return content
    
    def create_source_from_page(
        self,
        page: Dict[str, Any],
        twin_id: str,
        crawl_id: str
    ) -> Optional[str]:
        """
        Create a source record from a crawl page.
        
        Args:
            page: Crawl page record
            twin_id: Twin ID
            crawl_id: Crawl run ID
            
        Returns:
            Source ID if created, None otherwise
        """
        page_id = page.get("id", "")
        canonical_url = page.get("canonical_url", "")
        
        # Load content from artifact
        content = self.load_page_content(page, twin_id)
        if not content:
            logger.error(f"Cannot create source: no content for page {page_id}")
            return None
        
        # Generate source ID
        source_id = str(uuid.uuid4())
        
        # Build title from metadata or URL
        metadata = page.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        title = metadata.get("title", "")
        if not title:
            # Use URL path as fallback title
            from urllib.parse import urlparse
            parsed = urlparse(canonical_url)
            title = parsed.path.strip("/").split("/")[-1] or "Web Page"
        
        # Create source record
        source_data = {
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"Web: {title}"[:240],
            "file_size": len(content.encode("utf-8")),
            "content_text": content[:10000],  # Store snippet in DB
            "status": "processing",
            "staging_status": "staged",
            "extracted_text_length": len(content),
            "citation_url": canonical_url,
            "content_hash": page.get("content_hash"),
            # Crawl metadata for tracking
            "metadata": {
                "crawl_id": crawl_id,
                "crawl_page_id": page_id,
                "canonical_url": canonical_url,
                "content_type": "crawl",
                "source_type": "web_crawl",
            }
        }
        
        try:
            try:
                supabase.table("sources").insert(source_data).execute()
            except Exception as insert_error:
                message = str(insert_error).lower()
                if "staging_status" in message and "sources" in message:
                    fallback = dict(source_data)
                    fallback.pop("staging_status", None)
                    supabase.table("sources").insert(fallback).execute()
                else:
                    raise
            logger.info(f"Created source {source_id} from page {page_id}")
            return source_id
        except Exception as e:
            logger.error(f"Failed to create source for page {page_id}: {e}")
            return None
    
    async def index_page_chunks(
        self,
        page: Dict[str, Any],
        source_id: str,
        twin_id: str,
        crawl_id: str
    ) -> int:
        """
        Chunk and index a crawl page.
        
        Args:
            page: Crawl page record
            source_id: Source ID
            twin_id: Twin ID
            crawl_id: Crawl run ID
            
        Returns:
            Number of chunks indexed
        """
        # Load content
        content = self.load_page_content(page, twin_id)
        if not content:
            return 0
        
        # Get chunk version
        previous_page_id = page.get("previous_page_id")
        chunk_version = 1
        
        if previous_page_id:
            # This is a changed page, tombstone old chunks and increment version
            chunk_version = await self.version_manager.get_next_version(previous_page_id)
            await self.version_manager.tombstone_previous_version(previous_page_id)
        
        # Chunk content
        chunks = chunk_with_source_policy(content, source_type="web")
        if not chunks:
            logger.warning(f"No chunks generated for page {page.get('id')}")
            return 0
        
        # Get namespace
        from modules.retrieval import get_namespace
        from modules.delphi_namespace import resolve_creator_id_for_twin
        
        creator_id = resolve_creator_id_for_twin(twin_id)
        namespace = get_namespace(creator_id, twin_id)
        
        # Get Pinecone index
        index = get_pinecone_index()
        adapter = PineconeIndexAdapter(index)
        
        # Build vectors with version metadata
        vectors = []
        canonical_url = page.get("canonical_url", "")
        content_hash = page.get("content_hash", "")
        page_id = page.get("id", "")
        
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")
            chunk_id = f"{source_id}_{i}"
            
            # Get embedding
            embedding = get_embedding(chunk_text)
            
            # Build metadata
            metadata: Dict[str, Any] = {
                # Standard fields
                "text": chunk_text,
                "source_id": source_id,
                "twin_id": twin_id,
                "chunk_id": chunk_id,
                "filename": f"Web: {canonical_url}",
                "citation_url": canonical_url,
                "type": "web_crawl",
                "chunk_type": "web_content",
                "block_type": "content",
                "is_answer_text": True,
                
                # Versioning fields (Phase 2.2)
                "crawl_id": crawl_id,
                "crawl_page_id": page_id,
                "canonical_url": canonical_url,
                "content_hash": content_hash,
                "chunk_version": chunk_version,
                "is_current": True,
                "tombstoned_at": None,
            }
            
            vectors.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": metadata
            })
        
        # Upsert to Pinecone
        if vectors:
            adapter.upsert(vectors, namespace)
            logger.info(f"Indexed {len(vectors)} chunks for source {source_id}")
        
        # Update source status
        source_update = {
            "status": "live",
            "staging_status": "live",
            "chunk_count": len(vectors)
        }
        try:
            supabase.table("sources").update(source_update).eq("id", source_id).execute()
        except Exception as update_error:
            message = str(update_error).lower()
            if "staging_status" in message and "sources" in message:
                fallback = dict(source_update)
                fallback.pop("staging_status", None)
                supabase.table("sources").update(fallback).eq("id", source_id).execute()
            else:
                raise

        return len(vectors)
    
    async def process_page(
        self,
        page: Dict[str, Any],
        twin_id: str,
        crawl_id: str
    ) -> Dict[str, Any]:
        """
        Process a single crawl page through the ingestion pipeline.
        
        Args:
            page: Crawl page record
            twin_id: Twin ID
            crawl_id: Crawl run ID
            
        Returns:
            Result dict with status and metrics
        """
        page_id = page.get("id", "")
        
        # Check if should skip (standard checks)
        should_skip, reason = self.should_skip_ingestion(page, twin_id)
        if should_skip:
            logger.info(f"Skipping page {page_id}: {reason}")
            return {
                "page_id": page_id,
                "status": "skipped",
                "reason": reason,
                "chunks_indexed": 0
            }
        
        # Create source record
        source_id = self.create_source_from_page(page, twin_id, crawl_id)
        if not source_id:
            return {
                "page_id": page_id,
                "status": "error",
                "reason": "source_creation_failed",
                "chunks_indexed": 0
            }
        
        # Index chunks
        try:
            num_chunks = await self.index_page_chunks(page, source_id, twin_id, crawl_id)
            content = self.load_page_content(page, twin_id)
            word_count = len((content or "").split())
            return {
                "page_id": page_id,
                "status": "indexed",
                "source_id": source_id,
                "chunks_indexed": num_chunks,
                "word_count": word_count,
            }
        except Exception as e:
            logger.error(f"Failed to index page {page_id}: {e}")
            return {
                "page_id": page_id,
                "status": "error",
                "reason": str(e),
                "chunks_indexed": 0
            }
    
    async def process_crawl_for_ingestion(
        self,
        crawl_id: str,
        twin_id: Optional[str] = None,
        require_confirmation: bool = False,
        research_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process all pages in a crawl for ingestion.
        
        This is the main entry point for crawl ingestion.
        
        Phase 3.5: Added confirmation-gated mode for research runs.
        
        Args:
            crawl_id: Crawl run ID
            twin_id: Optional twin ID (looked up if not provided)
            require_confirmation: Phase 3.5 - If True, only ingest confirmed sources
            research_run_id: Phase 3.5 - Required when require_confirmation=True
            
        Returns:
            Statistics dict with:
            - pages_processed
            - sources_created
            - chunks_indexed
            - pages_skipped_unchanged
            - pages_failed
            - Phase 3.5: pages_skipped_not_confirmed
            - Phase 3.5: pages_skipped_rejected
            - Phase 3.5: confirmation_gate_enabled
        """
        # Phase 3.5: Validate parameters
        if require_confirmation and not research_run_id:
            raise ValueError("research_run_id is required when require_confirmation=True")
        
        # Get crawl run
        crawl_run = self.repository.get_crawl_run(crawl_id)
        if not crawl_run:
            raise ValueError(f"Crawl run not found: {crawl_id}")
        
        # Use twin_id from crawl run if not provided
        if not twin_id:
            twin_id = crawl_run.get("twin_id", "")
        
        if not twin_id:
            raise ValueError(f"No twin_id found for crawl {crawl_id}")
        
        # Get all pages for this crawl
        pages = self.repository.get_pages_by_crawl(crawl_id)
        
        # Phase 3.5: Build confirmed page set if in gated mode
        confirmed_page_ids: Set[str] = set()
        if require_confirmation and research_run_id:
            confirmed_page_ids = await self._get_confirmed_page_ids(research_run_id, twin_id)
            logger.info(f"Phase 3.5: Confirmation gate enabled. {len(confirmed_page_ids)}/{len(pages)} pages confirmed for ingestion")
        
        # Statistics
        stats = {
            "pages_processed": 0,
            "sources_created": 0,
            "chunks_indexed": 0,
            "total_words": 0,
            "pages_skipped_unchanged": 0,
            "pages_failed": 0,
            "pages_skipped_no_artifact": 0,
            # Phase 3.5 stats
            "confirmation_gate_enabled": require_confirmation,
            "pages_skipped_not_confirmed": 0,
            "pages_skipped_rejected": 0,
            "pages_confirmed_eligible": len(confirmed_page_ids) if require_confirmation else 0,
        }
        
        logger.info(f"Processing {len(pages)} pages for crawl {crawl_id}")
        
        for page in pages:
            page_id = page.get("id", "")
            
            # Phase 3.5: Check confirmation gate first if enabled
            if require_confirmation:
                should_skip, gate_reason = self.should_skip_ingestion_confirmation_gate(
                    page, confirmed_page_ids
                )
                if should_skip:
                    if gate_reason == "not_confirmed":
                        # Check if specifically rejected or just pending
                        stats["pages_skipped_not_confirmed"] += 1
                    else:
                        stats["pages_skipped_rejected"] += 1
                    
                    logger.debug(f"Phase 3.5: Skipping page {page_id}: {gate_reason}")
                    stats["pages_processed"] += 1
                    continue
            
            # Standard page processing
            result = await self.process_page(page, twin_id, crawl_id)
            
            stats["pages_processed"] += 1
            
            if result["status"] == "skipped":
                if result.get("reason") == "unchanged_content":
                    stats["pages_skipped_unchanged"] += 1
                else:
                    stats["pages_skipped_no_artifact"] += 1
            elif result["status"] == "error":
                stats["pages_failed"] += 1
            elif result["status"] == "indexed":
                stats["sources_created"] += 1
                stats["chunks_indexed"] += result.get("chunks_indexed", 0)
                stats["total_words"] += result.get("word_count", 0)
        
        logger.info(f"Crawl ingestion complete: {stats}")
        
        # Update crawl run with ingestion stats
        self.repository.update_crawl_stats(
            crawl_id=crawl_id,
            pages_found=len(pages),
            pages_ingested=stats["sources_created"],
            pages_failed=stats["pages_failed"],
            pages_unchanged=stats["pages_skipped_unchanged"]
        )
        
        return stats
    
    async def _get_confirmed_page_ids(
        self,
        research_run_id: str,
        twin_id: str
    ) -> Set[str]:
        """
        Phase 3.5: Get set of confirmed page IDs for a research run.
        
        Only includes statuses: confirmed, auto_confirmed
        Excludes: pending, manual_review, rejected, auto_rejected
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            
        Returns:
            Set of crawl_page_id strings that are confirmed
        """
        try:
            response = supabase.table("source_confirmations").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
        except Exception as e:
            logger.error(f"Phase 3.5: Error fetching confirmed pages: {e}")
            # Fail safe: return empty set (no pages will be ingested)
            return set()

        rows = response.data or []
        if not rows:
            return set()

        confirmed_ids = set()
        for row in rows:
            status_value = (
                row.get("confirmation_status")
                or row.get("status")
                or row.get("state")
                or ""
            )
            if status_value not in ("confirmed", "auto_confirmed"):
                continue
            page_id = row.get("crawl_page_id")
            if page_id:
                confirmed_ids.add(page_id)

        logger.debug(f"Phase 3.5: Found {len(confirmed_ids)} confirmed pages for research run {research_run_id}")
        return confirmed_ids


# Convenience function
async def ingest_crawl(
    crawl_id: str,
    twin_id: Optional[str] = None,
    require_confirmation: bool = False,
    research_run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to ingest a crawl.
    
    Phase 3.5: Added confirmation-gated mode.
    
    Args:
        crawl_id: Crawl run ID
        twin_id: Optional twin ID
        require_confirmation: Phase 3.5 - If True, only ingest confirmed sources
        research_run_id: Phase 3.5 - Required when require_confirmation=True
        
    Returns:
        Ingestion statistics
    """
    bridge = CrawlIngestionBridge()
    return await bridge.process_crawl_for_ingestion(
        crawl_id=crawl_id,
        twin_id=twin_id,
        require_confirmation=require_confirmation,
        research_run_id=research_run_id
    )
