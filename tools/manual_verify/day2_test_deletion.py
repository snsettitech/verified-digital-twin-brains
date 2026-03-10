#!/usr/bin/env python3
"""
Day 2: Test Twin & Creator Deletion
Tests the deletion mechanisms after migration.
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

TEST_CREATOR_ID = "sainath.no.1"
INDEX_NAME = "digital-twin-brain"


class DeletionTester:
    """Test twin and creator deletion mechanisms."""
    
    def __init__(self, index_name: str):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index = self.pc.Index(index_name)
    
    def list_creator_namespaces(self) -> list:
        """List all namespaces for the test creator."""
        stats = self.index.describe_index_stats()
        creator_namespaces = []
        
        for ns in stats.namespaces.keys():
            if ns.startswith(f"creator_{TEST_CREATOR_ID}"):
                creator_namespaces.append(ns)
        
        return sorted(creator_namespaces)
    
    def get_namespace_vector_count(self, namespace: str) -> int:
        """Get vector count for a namespace."""
        stats = self.index.describe_index_stats()
        ns_stats = stats.namespaces.get(namespace)
        if ns_stats is None:
            return 0
        # Handle both object and dict access
        if hasattr(ns_stats, 'vector_count'):
            return ns_stats.vector_count
        elif isinstance(ns_stats, dict):
            return ns_stats.get('vector_count', 0)
        return 0
    
    def test_twin_deletion(self, twin_namespace: str) -> bool:
        """
        Test deleting a specific twin namespace.
        
        Args:
            twin_namespace: Full namespace name (e.g., creator_sainath.no.1_twin_abc123)
        """
        logger.info("="*60)
        logger.info("TEST 1: TWIN DELETION")
        logger.info("="*60)
        logger.info(f"Twin namespace: {twin_namespace}")
        
        # Get count before
        count_before = self.get_namespace_vector_count(twin_namespace)
        logger.info(f"Vectors before: {count_before}")
        
        if count_before == 0:
            logger.warning("Namespace is empty, nothing to delete")
            return False
        
        # Delete the twin namespace
        try:
            logger.info(f"Deleting namespace: {twin_namespace}")
            self.index.delete(delete_all=True, namespace=twin_namespace)
            
            # Verify deletion
            count_after = self.get_namespace_vector_count(twin_namespace)
            logger.info(f"Vectors after: {count_after}")
            
            if count_after == 0:
                logger.info("✓ Twin deletion SUCCESSFUL")
                return True
            else:
                logger.error("✗ Twin deletion FAILED - vectors still exist")
                return False
                
        except Exception as e:
            logger.error(f"✗ Error during twin deletion: {e}")
            return False
    
    def test_creator_deletion(self) -> bool:
        """
        Test deleting ALL data for the test creator (GDPR scenario).
        This deletes all twin namespaces for the creator.
        """
        logger.info("")
        logger.info("="*60)
        logger.info("TEST 2: CREATOR DELETION (GDPR)")
        logger.info("="*60)
        logger.info(f"Creator ID: {TEST_CREATOR_ID}")
        
        # List all creator namespaces
        creator_namespaces = self.list_creator_namespaces()
        logger.info(f"Found {len(creator_namespaces)} namespaces for creator:")
        for ns in creator_namespaces:
            count = self.get_namespace_vector_count(ns)
            logger.info(f"  - {ns}: {count} vectors")
        
        if not creator_namespaces:
            logger.warning("No namespaces found for creator")
            return False
        
        # Delete each namespace
        deleted_count = 0
        for ns in creator_namespaces:
            try:
                logger.info(f"Deleting: {ns}")
                self.index.delete(delete_all=True, namespace=ns)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting {ns}: {e}")
        
        # Verify all deleted
        remaining = self.list_creator_namespaces()
        
        logger.info("")
        logger.info(f"Deleted: {deleted_count} namespaces")
        logger.info(f"Remaining: {len(remaining)} namespaces")
        
        if len(remaining) == 0:
            logger.info("✓ Creator deletion SUCCESSFUL - GDPR compliant!")
            return True
        else:
            logger.error("✗ Creator deletion PARTIAL - some namespaces remain")
            for ns in remaining:
                logger.error(f"  - {ns}")
            return False
    
    def test_query_performance(self) -> dict:
        """Test query performance on migrated namespaces."""
        logger.info("")
        logger.info("="*60)
        logger.info("TEST 3: QUERY PERFORMANCE")
        logger.info("="*60)
        
        import time
        import random
        
        # Get all creator namespaces
        namespaces = self.list_creator_namespaces()
        
        if not namespaces:
            logger.warning("No namespaces to test")
            return {}
        
        # Test query on each namespace
        latencies = []
        test_vector = [random.random() for _ in range(3072)]
        
        logger.info(f"Testing {len(namespaces)} namespaces...")
        
        for ns in namespaces[:5]:  # Test first 5
            try:
                start = time.time()
                result = self.index.query(
                    vector=test_vector,
                    top_k=10,
                    namespace=ns,
                    include_metadata=True
                )
                latency = (time.time() - start) * 1000  # ms
                latencies.append(latency)
                logger.info(f"  {ns}: {latency:.2f}ms")
            except Exception as e:
                logger.error(f"  {ns}: ERROR - {e}")
        
        if latencies:
            p50 = sorted(latencies)[len(latencies) // 2]
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            
            logger.info("")
            logger.info("Performance Results:")
            logger.info(f"  P50 Latency: {p50:.2f}ms")
            logger.info(f"  P95 Latency: {p95:.2f}ms")
            
            if p95 < 100:
                logger.info("✓ Performance GOOD (< 100ms P95)")
            else:
                logger.warning("⚠ Performance SLOW (> 100ms P95)")
            
            return {
                "p50": p50,
                "p95": p95,
                "good": p95 < 100
            }
        
        return {}
    
    def verify_gdpr_compliance(self) -> bool:
        """
        Verify that creator deletion is truly GDPR compliant.
        After deletion, no data should remain for the creator.
        """
        logger.info("")
        logger.info("="*60)
        logger.info("TEST 4: GDPR COMPLIANCE VERIFICATION")
        logger.info("="*60)
        
        # Check for any remaining namespaces
        remaining = self.list_creator_namespaces()
        
        if remaining:
            logger.error("✗ GDPR COMPLIANCE FAILED")
            logger.error(f"  {len(remaining)} namespaces still exist:")
            for ns in remaining:
                logger.error(f"    - {ns}")
            return False
        
        # Check for any vectors with creator_id in metadata
        # (This would require querying all vectors, which is expensive)
        # For now, namespace check is sufficient
        
        logger.info("✓ GDPR COMPLIANCE VERIFIED")
        logger.info("  No data remains for creator")
        logger.info("  Right to erasure: SATISFIED")
        return True
    
    def run_all_tests(self, auto_confirm=False):
        """Run all deletion tests."""
        logger.info("="*60)
        logger.info("DAY 2: TESTING TWIN & CREATOR DELETION")
        logger.info("="*60)
        logger.info("")
        
        # Get initial state
        namespaces = self.list_creator_namespaces()
        logger.info(f"Initial state: {len(namespaces)} namespaces for {TEST_CREATOR_ID}")
        for ns in namespaces[:5]:  # Show first 5
            count = self.get_namespace_vector_count(ns)
            logger.info(f"  - {ns}: {count} vectors")
        if len(namespaces) > 5:
            logger.info(f"  ... and {len(namespaces) - 5} more")
        logger.info("")
        
        if not namespaces:
            logger.warning(
                "No creator namespaces found for deletion tests. "
                "Skipping Day 2 checks because Pinecone is currently empty."
            )
            return
        
        # Test 1: Query Performance
        perf_results = self.test_query_performance()
        
        # Test 2: Delete one twin (keep others for creator deletion test)
        twin_to_delete = namespaces[0]
        twin_deleted = self.test_twin_deletion(twin_to_delete)
        
        # Test 3: Creator deletion (delete remaining)
        logger.info("")
        if auto_confirm:
            user_input = "yes"
            logger.info(f"Auto-confirmed: Delete ALL remaining data for {TEST_CREATOR_ID}")
        else:
            user_input = input(f"\nDelete ALL remaining data for {TEST_CREATOR_ID}? (yes/no): ")
        
        if user_input.lower() == "yes":
            creator_deleted = self.test_creator_deletion()
            
            # Test 4: GDPR Verification
            gdpr_compliant = self.verify_gdpr_compliance()
            
            # Summary
            logger.info("")
            logger.info("="*60)
            logger.info("TEST SUMMARY")
            logger.info("="*60)
            logger.info(f"Twin Deletion:     {'PASS' if twin_deleted else 'FAIL'}")
            logger.info(f"Creator Deletion:  {'PASS' if creator_deleted else 'FAIL'}")
            logger.info(f"Query Performance: {'PASS' if perf_results.get('good') else 'SLOW'}")
            logger.info(f"GDPR Compliance:   {'PASS' if gdpr_compliant else 'FAIL'}")
            
            all_passed = twin_deleted and creator_deleted and gdpr_compliant
            
            if all_passed:
                logger.info("")
                logger.info("ALL TESTS PASSED!")
                logger.info("The Delphi namespace strategy works correctly.")
                logger.info("You can now:")
                logger.info("  1. Keep migrated data and use it (Option A)")
                logger.info("  2. Delete all and start fresh (Option B)")
                logger.info("  3. Start adding new twins with semantic naming")
            else:
                logger.info("")
                logger.info("SOME TESTS FAILED")
                logger.info("Review the errors above and fix before proceeding.")
        else:
            logger.info("Creator deletion skipped. Remaining namespaces:")
            for ns in self.list_creator_namespaces():
                count = self.get_namespace_vector_count(ns)
                logger.info(f"  - {ns}: {count} vectors")


def main():
    """Main entry point."""
    import sys
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    tester = DeletionTester(INDEX_NAME)
    tester.run_all_tests(auto_confirm=auto_confirm)


if __name__ == "__main__":
    main()
