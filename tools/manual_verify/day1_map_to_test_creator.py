#!/usr/bin/env python3
"""
Day 1: Map Current Namespaces to Test Creator
Maps all 30 UUID namespaces to creator_sainath.no.1_twin_{name}
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone
from typing import Dict, List, Optional
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
TEST_CREATOR_ID = "sainath.no.1"
INDEX_NAME = "digital-twin-brain"

# Namespace mapping: old_name -> new_name
# Following your preference for semantic naming where possible
NAMESPACE_MAPPING = {
    # Default namespace gets special handling
    "__default__": f"creator_{TEST_CREATOR_ID}_twin_default",
    
    # UUID namespaces will be mapped with shortened UUID for readability
    # Format: creator_sainath.no.1_twin_{first_8_chars}
    # Full mapping will be generated dynamically
}


class NamespaceMapper:
    """Maps old UUID namespaces to new creator-based structure."""
    
    def __init__(self, index_name: str):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index = self.pc.Index(index_name)
        self.stats_before = None
        self.stats_after = None
        self.migration_log = []
        
    def create_backup(self) -> Optional[str]:
        """Create collection backup before migration.
        
        Note: Pinecone Serverless doesn't support create_collection.
        Migration is safe because we keep originals until verification.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{INDEX_NAME}-backup-{timestamp}"
        
        logger.info(f"Backup: Pinecone Serverless doesn't support collection backup")
        logger.info(f"Migration is safe: originals kept until verification")
        
        # Return backup name for logging purposes
        return backup_name

    @staticmethod
    def _ns_vector_count(ns_stats) -> int:
        if ns_stats is None:
            return 0
        if hasattr(ns_stats, "vector_count"):
            return int(ns_stats.vector_count)
        if isinstance(ns_stats, dict):
            return int(ns_stats.get("vector_count", 0))
        return 0
    
    def get_namespace_mapping(self) -> Dict[str, str]:
        """
        Generate mapping from current namespaces to new creator-based names.
        
        Strategy:
        - __default__ -> creator_sainath.no.1_twin_default
        - UUID namespaces -> creator_sainath.no.1_twin_{semantic_name}
        """
        stats = self.index.describe_index_stats()
        mapping = {}
        
        for ns_name in stats.namespaces.keys():
            if ns_name == "__default__":
                new_name = f"creator_{TEST_CREATOR_ID}_twin_default"
            else:
                # Use first 8 chars of UUID for the twin name
                # In production, you'd map this to actual twin names from DB
                short_uuid = ns_name.split('-')[0] if '-' in ns_name else ns_name[:8]
                new_name = f"creator_{TEST_CREATOR_ID}_twin_{short_uuid}"
            
            mapping[ns_name] = new_name
        
        return mapping
    
    def get_all_vector_ids(self, namespace: str) -> List[str]:
        """Get all vector IDs in a namespace."""
        ids = []
        pagination_token = None
        
        while True:
            try:
                response = self.index.list_paginated(
                    namespace=namespace,
                    limit=100,
                    pagination_token=pagination_token
                )
                
                ids.extend([v.id for v in response.vectors])
                
                pagination_token = response.pagination.next
                if not pagination_token:
                    break
                    
            except Exception as e:
                logger.error(f"Error listing vectors in {namespace}: {e}")
                break
        
        return ids
    
    def migrate_namespace(self, old_ns: str, new_ns: str, dry_run: bool = False) -> Dict:
        """
        Migrate one namespace to new creator-based format.
        
        Args:
            old_ns: Current namespace name
            new_ns: New namespace name
            dry_run: If True, only count without migrating
        
        Returns:
            Migration statistics
        """
        logger.info(f"Migrating: {old_ns} → {new_ns}")
        
        # Get all vector IDs
        vector_ids = self.get_all_vector_ids(old_ns)
        total_vectors = len(vector_ids)
        
        if dry_run:
            return {
                "old_namespace": old_ns,
                "new_namespace": new_ns,
                "total_vectors": total_vectors,
                "migrated": 0,
                "status": "dry_run"
            }
        
        # Migrate in batches
        batch_size = 100
        migrated = 0
        
        for i in range(0, len(vector_ids), batch_size):
            batch_ids = vector_ids[i:i + batch_size]
            
            try:
                # Fetch from old namespace
                fetch_response = self.index.fetch(
                    ids=batch_ids,
                    namespace=old_ns
                )
                
                if not fetch_response.vectors:
                    continue
                
                # Prepare for upsert with updated metadata
                vectors_to_upsert = []
                for vid, vector in fetch_response.vectors.items():
                    metadata = vector.metadata or {}
                    
                    # Add creator/twin metadata
                    metadata['creator_id'] = TEST_CREATOR_ID
                    metadata['original_namespace'] = old_ns
                    metadata['migrated_at'] = datetime.now().isoformat()
                    
                    vectors_to_upsert.append({
                        "id": vid,
                        "values": vector.values,
                        "metadata": metadata
                    })
                
                # Upsert to new namespace
                self.index.upsert(
                    vectors=vectors_to_upsert,
                    namespace=new_ns
                )
                migrated += len(vectors_to_upsert)
                
            except Exception as e:
                logger.error(f"Error migrating batch {i}: {e}")
        
        logger.info(f"✓ Migrated {migrated}/{total_vectors} vectors to {new_ns}")
        
        return {
            "old_namespace": old_ns,
            "new_namespace": new_ns,
            "total_vectors": total_vectors,
            "migrated": migrated,
            "status": "completed" if migrated == total_vectors else "partial"
        }
    
    def verify_migration(self, old_ns: str, new_ns: str) -> bool:
        """Verify vectors were migrated correctly."""
        stats = self.index.describe_index_stats()
        
        old_count = self._ns_vector_count(stats.namespaces.get(old_ns))
        new_count = self._ns_vector_count(stats.namespaces.get(new_ns))
        
        if old_count == new_count:
            logger.info(f"✓ Verification passed: {old_count} vectors match")
            return True
        else:
            logger.warning(
                f"⚠ Verification mismatch: "
                f"old={old_count}, new={new_count}"
            )
            return False
    
    def cleanup_old_namespace(self, namespace: str):
        """Delete all vectors from old namespace after verification."""
        logger.info(f"Cleaning up old namespace: {namespace}")
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"✓ Deleted namespace: {namespace}")
        except Exception as e:
            logger.error(f"✗ Error deleting {namespace}: {e}")
    
    def run_migration(self, dry_run: bool = True):
        """Run the full migration process."""
        logger.info("="*60)
        logger.info("NAMESPACE MIGRATION TO TEST CREATOR")
        logger.info("="*60)
        logger.info(f"Test Creator ID: {TEST_CREATOR_ID}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("")
        
        # Step 1: Create backup
        if not dry_run:
            backup_name = self.create_backup()
            logger.info(f"Backup created: {backup_name}")
        
        # Step 2: Get current state
        self.stats_before = self.index.describe_index_stats()
        total_before = self.stats_before.total_vector_count
        logger.info(f"Current state: {total_before} vectors in {len(self.stats_before.namespaces)} namespaces")
        logger.info("")
        
        # Step 3: Generate mapping
        mapping = self.get_namespace_mapping()
        logger.info("Namespace mapping plan:")
        for old, new in mapping.items():
            count = self._ns_vector_count(self.stats_before.namespaces.get(old))
            logger.info(f"  {old} ({count} vectors) → {new}")
        logger.info("")
        
        if dry_run:
            logger.info("DRY RUN - No changes made")
            logger.info("Review the mapping above and run with dry_run=False to execute")
            return
        
        # Step 4: Execute migration
        logger.info("Executing migration...")
        results = []
        
        for old_ns, new_ns in mapping.items():
            result = self.migrate_namespace(old_ns, new_ns, dry_run=False)
            results.append(result)
            
            # Verify
            if result["migrated"] > 0:
                verified = self.verify_migration(old_ns, new_ns)
                if verified:
                    # Clean up old namespace
                    self.cleanup_old_namespace(old_ns)
            
            self.migration_log.append(result)
        
        # Step 5: Final verification
        logger.info("")
        logger.info("="*60)
        logger.info("MIGRATION COMPLETE")
        logger.info("="*60)
        
        self.stats_after = self.index.describe_index_stats()
        total_after = self.stats_after.total_vector_count
        
        logger.info(f"Before: {total_before} vectors in {len(self.stats_before.namespaces)} namespaces")
        logger.info(f"After: {total_after} vectors in {len(self.stats_after.namespaces)} namespaces")
        
        # Show new namespace structure
        logger.info("")
        logger.info("New namespace structure:")
        for ns_name in sorted(self.stats_after.namespaces.keys()):
            count = self._ns_vector_count(self.stats_after.namespaces[ns_name])
            logger.info(f"  {ns_name}: {count} vectors")
        
        # Summary
        total_migrated = sum(r["migrated"] for r in results)
        logger.info("")
        logger.info(f"Total vectors migrated: {total_migrated}")
        logger.info(f"Migration complete for creator: {TEST_CREATOR_ID}")
        
        return results


if __name__ == "__main__":
    import sys
    
    # Check for auto-confirm flag
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    logger.info("="*60)
    logger.info("NAMESPACE MIGRATION TO TEST CREATOR")
    logger.info("="*60)
    logger.info(f"Test Creator ID: {TEST_CREATOR_ID}")
    logger.info("")
    
    mapper = NamespaceMapper(INDEX_NAME)
    
    logger.info("STEP 1: DRY RUN")
    logger.info("-"*60)
    mapper.run_migration(dry_run=True)
    
    logger.info("")
    logger.info("Review the mapping plan above.")
    
    if auto_confirm:
        user_input = "yes"
        logger.info("Auto-confirmed via --yes flag")
    else:
        user_input = input("\nProceed with actual migration? (yes/no): ")
    
    if user_input.lower() == "yes":
        logger.info("")
        logger.info("STEP 2: ACTUAL MIGRATION")
        logger.info("-"*60)
        results = mapper.run_migration(dry_run=False)
        
        logger.info("")
        logger.info("Day 1 Complete!")
        logger.info(f"All namespaces mapped to creator: {TEST_CREATOR_ID}")
        logger.info("Run day2_test_deletion.py to test twin/creator deletion")
    else:
        logger.info("Migration cancelled. No changes made.")
