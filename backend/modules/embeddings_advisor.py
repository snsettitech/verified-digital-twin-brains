#!/usr/bin/env python3
"""
creator-scoped Pinecone Client with Creator-Based Namespaces

This module provides a new embedding client that uses the creator namespace strategy:
- Twin-specific: creator_{creator_id}_twin_{twin_id}
- Creator-wide: creator_{creator_id}

Benefits:
- GDPR compliance (easy creator deletion)
- Multi-twin search capability
- Scalable to 25,000 namespaces
- Cost-effective (inactive namespaces don't consume compute)
"""
import os
from typing import Optional, List, Dict, Any
from pinecone import Pinecone
import logging

logger = logging.getLogger(__name__)


class PineconeAdvisorClient:
    """
    Pinecone client using creator namespace strategy.
    
    Namespace naming convention:
    - Twin-specific: creator_{creator_id}_twin_{twin_id}
    - Creator-wide: creator_{creator_id}
    """
    
    def __init__(
        self,
        index_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the advisor client.
        
        Args:
            index_name: Pinecone index name (default: digital-twin-brain)
        """
        resolved_index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "digital-twin-brain")

        if api_key:
            # Explicit key provided (tests or multi-account) — create dedicated client
            self.pc = Pinecone(api_key=api_key)
        else:
            # Use the shared singleton from clients.py to avoid duplicate connections
            from modules.clients import get_pinecone_client
            self.pc = get_pinecone_client()

        self.index = self.pc.Index(resolved_index_name)
        self.index_name = resolved_index_name
        
        logger.info(f"advisor client initialized for index: {resolved_index_name}")
    
    def _get_namespace(
        self,
        creator_id: str,
        twin_id: Optional[str] = None
    ) -> str:
        """
        Generate namespace name based on creator and twin.
        
        Args:
            creator_id: Creator identifier (e.g., "sainath.no.1")
            twin_id: Optional twin identifier (e.g., "coach_persona")
        
        Returns:
            Namespace string
        """
        if twin_id:
            return f"creator_{creator_id}_twin_{twin_id}"
        return f"creator_{creator_id}"

    def get_namespace(self, creator_id: str, twin_id: Optional[str] = None) -> str:
        """Public namespace helper."""
        return self._get_namespace(creator_id, twin_id)
    
    def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        creator_id: str,
        twin_id: Optional[str] = None
    ) -> Dict:
        """
        Upsert vectors with creator/twin metadata.
        
        Args:
            vectors: List of vectors with format:
                [
                    {
                        "id": "doc-1",
                        "values": [0.1, 0.2, ...],  # 3072 dimensions
                        "metadata": {"text": "...", "source": "..."}
                    }
                ]
            creator_id: Creator identifier
            twin_id: Optional twin identifier
        
        Returns:
            Upsert response from Pinecone
        """
        namespace = self._get_namespace(creator_id, twin_id)
        
        # Enrich metadata with creator/twin info
        for vector in vectors:
            if not vector.get("metadata"):
                vector["metadata"] = {}
            
            vector["metadata"]["creator_id"] = creator_id
            if twin_id:
                vector["metadata"]["twin_id"] = twin_id
        
        try:
            response = self.index.upsert(
                vectors=vectors,
                namespace=namespace
            )
            logger.info(
                f"Upserted {len(vectors)} vectors to {namespace}"
            )
            return response
        except Exception as e:
            logger.error(f"Upsert failed: {e}")
            raise
    
    def query(
        self,
        vector: List[float],
        creator_id: str,
        twin_id: Optional[str] = None,
        top_k: int = 10,
        filter: Optional[Dict] = None,
        include_metadata: bool = True
    ) -> Any:
        """
        Query vectors in creator's namespace.
        
        Args:
            vector: Query embedding (3072 dimensions)
            creator_id: Creator identifier
            twin_id: If None, queries creator-wide namespace
            top_k: Number of results to return
            filter: Metadata filter (e.g., {"category": "tech"})
            include_metadata: Whether to include metadata in results
        
        Returns:
            Pinecone query response with matches
        """
        namespace = self._get_namespace(creator_id, twin_id)
        
        try:
            response = self.index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter,
                include_metadata=include_metadata
            )
            return response
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
    
    def query_across_twins(
        self,
        vector: List[float],
        creator_id: str,
        twin_ids: List[str],
        top_k: int = 10,
        include_metadata: bool = True
    ) -> List[Any]:
        """
        Query across multiple twins for a creator and merge results.
        
        This is useful for searching across all creator's twins.
        
        Args:
            vector: Query embedding
            creator_id: Creator identifier
            twin_ids: List of twin IDs to search across
            top_k: Number of top results to return after merging
            include_metadata: Whether to include metadata
        
        Returns:
            Merged and re-ranked list of matches
        """
        all_matches = []
        
        for twin_id in twin_ids:
            try:
                results = self.query(
                    vector=vector,
                    creator_id=creator_id,
                    twin_id=twin_id,
                    top_k=top_k,
                    include_metadata=include_metadata
                )
                all_matches.extend(results.matches)
            except Exception as e:
                logger.warning(f"Query failed for twin {twin_id}: {e}")
        
        # Re-rank by score
        all_matches.sort(key=lambda x: x.score, reverse=True)
        
        return all_matches[:top_k]

    def query_text(
        self,
        query_vector: List[float],
        creator_id: str,
        twin_id: str,
        top_k: int = 10,
    ) -> Any:
        """
        Compatibility helper for callers that already computed embeddings.
        """
        return self.query(
            vector=query_vector,
            creator_id=creator_id,
            twin_id=twin_id,
            top_k=top_k,
            include_metadata=True,
        )
    
    def delete_twin(self, creator_id: str, twin_id: str) -> bool:
        """
        Delete all vectors for a specific twin.
        
        Args:
            creator_id: Creator identifier
            twin_id: Twin identifier
        
        Returns:
            True if successful
        """
        namespace = self._get_namespace(creator_id, twin_id)
        
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted twin namespace: {namespace}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete twin: {e}")
            return False
    
    def delete_creator_data(self, creator_id: str) -> bool:
        """
        Delete ALL data for a creator (GDPR compliance).
        
        This deletes:
        - Creator-wide namespace (creator_{id})
        - All twin namespaces (creator_{id}_twin_*)
        
        Args:
            creator_id: Creator identifier
        
        Returns:
            True if all data deleted successfully
        """
        deleted_count = 0
        failed_count = 0
        
        # Get all namespaces for this creator
        stats = self.index.describe_index_stats()
        creator_namespaces = [
            ns for ns in stats.namespaces.keys()
            if ns.startswith(f"creator_{creator_id}")
        ]
        
        logger.info(
            f"Deleting {len(creator_namespaces)} namespaces for {creator_id}"
        )
        
        for namespace in creator_namespaces:
            try:
                self.index.delete(delete_all=True, namespace=namespace)
                logger.info(f"  Deleted: {namespace}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"  Failed to delete {namespace}: {e}")
                failed_count += 1
        
        logger.info(
            f"Creator deletion complete: {deleted_count} deleted, "
            f"{failed_count} failed"
        )
        
        return failed_count == 0

    def delete_creator(self, creator_id: str) -> int:
        """
        Compatibility alias that returns deleted namespace count.
        """
        deleted = 0
        stats = self.index.describe_index_stats()
        namespaces = [
            ns for ns in stats.namespaces.keys()
            if ns.startswith(f"creator_{creator_id}")
        ]
        for namespace in namespaces:
            self.index.delete(delete_all=True, namespace=namespace)
            deleted += 1
        return deleted
    
    def list_creator_twins(self, creator_id: str) -> List[Dict]:
        """
        List all twins for a creator.
        
        Args:
            creator_id: Creator identifier
        
        Returns:
            List of twin info dicts with keys: twin_id, namespace, vector_count
        """
        stats = self.index.describe_index_stats()
        twins = []
        
        prefix = f"creator_{creator_id}_twin_"
        
        for namespace, ns_stats in stats.namespaces.items():
            if namespace.startswith(prefix):
                twin_id = namespace[len(prefix):]
                twins.append({
                    "twin_id": twin_id,
                    "namespace": namespace,
                    "vector_count": ns_stats.vector_count
                })
        
        return sorted(twins, key=lambda x: x["twin_id"])

    def list_twins_for_creator(self, creator_id: str) -> List[str]:
        """Compatibility helper returning only twin ids."""
        return [t["twin_id"] for t in self.list_creator_twins(creator_id)]

    def list_namespaces_for_creator(self, creator_id: str) -> List[str]:
        """List namespace names for a creator."""
        stats = self.index.describe_index_stats()
        prefix = f"creator_{creator_id}"
        return sorted([ns for ns in stats.namespaces.keys() if ns.startswith(prefix)])
    
    def get_twin_stats(self, creator_id: str, twin_id: str) -> Dict:
        """
        Get statistics for a specific twin.
        
        Args:
            creator_id: Creator identifier
            twin_id: Twin identifier
        
        Returns:
            Stats dict with vector_count and namespace
        """
        namespace = self._get_namespace(creator_id, twin_id)
        stats = self.index.describe_index_stats()
        
        ns_stats = stats.namespaces.get(namespace)
        if ns_stats:
            return {
                "namespace": namespace,
                "vector_count": ns_stats.vector_count,
                "exists": True
            }
        
        return {
            "namespace": namespace,
            "vector_count": 0,
            "exists": False
        }
    
    def verify_gdpr_deletion(self, creator_id: str) -> bool:
        """
        Verify that all data for a creator has been deleted (GDPR check).
        
        Args:
            creator_id: Creator identifier
        
        Returns:
            True if no data remains for creator
        """
        stats = self.index.describe_index_stats()
        
        # Check for any namespaces for this creator
        for ns in stats.namespaces.keys():
            if ns.startswith(f"creator_{creator_id}"):
                logger.error(f"GDPR check failed: namespace exists - {ns}")
                return False
        
        logger.info(f"GDPR check passed: no data for {creator_id}")
        return True


# Singleton instance for application use
_advisor_client = None

def get_advisor_client(index_name: str = "digital-twin-brain") -> PineconeAdvisorClient:
    """
    Get or create singleton advisor client.
    
    Args:
        index_name: Pinecone index name
    
    Returns:
        PineconeAdvisorClient instance
    """
    global _advisor_client
    if _advisor_client is None:
        _advisor_client = PineconeAdvisorClient(index_name)
    return _advisor_client


def reset_advisor_client():
    """Reset singleton (useful for testing)."""
    global _advisor_client
    _advisor_client = None
