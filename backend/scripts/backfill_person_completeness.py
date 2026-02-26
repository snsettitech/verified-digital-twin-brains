"""
Backfill Script for Person Completeness v1

Runs the person completeness pipeline for existing twins.
Usage:
    python -m scripts.backfill_person_completeness --twin-id <twin_id>
    python -m scripts.backfill_person_completeness --all-twins --batch-size 10
"""

import argparse
import asyncio
import logging
import sys
from typing import List
from datetime import datetime
from pathlib import Path

# Ensure `modules.*` imports work whether executed from repo root or backend dir.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_twin_ids() -> List[str]:
    """Get all twin IDs from database."""
    try:
        from modules.observability import supabase

        response = supabase.table("twins").select("id").execute()
        return [t["id"] for t in response.data] if response.data else []
    except Exception as e:
        logger.error(f"Error fetching twins: {e}")
        return []


def get_twins_needing_backfill() -> List[str]:
    """Get twins that haven't been processed yet."""
    try:
        from modules.observability import supabase

        # Get twins with no completeness run or old run
        response = supabase.table("twins") \
            .select("id, person_completeness_runs(status, created_at)") \
            .execute()

        needs_backfill = []
        for twin in response.data:
            runs = twin.get("person_completeness_runs", [])
            if not runs:
                needs_backfill.append(twin["id"])
            else:
                # Check if latest run is older than 7 days
                latest = max(runs, key=lambda x: x.get("created_at", ""))
                run_date = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
                days_since = (datetime.now() - run_date).days
                if days_since > 7:
                    needs_backfill.append(twin["id"])

        return needs_backfill
    except Exception as e:
        logger.error(f"Error checking backfill status: {e}")
        return []


async def backfill_twin(twin_id: str, force: bool = False) -> dict:
    """Run pipeline for a single twin."""
    try:
        from modules.person_completeness_pipeline import run_person_completeness_pipeline

        logger.info(f"Processing twin {twin_id}...")
        result = await run_person_completeness_pipeline(
            twin_id=twin_id,
            force_rebuild=force
        )

        if result.success:
            logger.info(f"[OK] Twin {twin_id}: {len(result.stages_completed)} stages completed")
        else:
            logger.warning(f"[FAILED] Twin {twin_id}: {result.error_message}")

        return {
            "twin_id": twin_id,
            "success": result.success,
            "stages": len(result.stages_completed),
            "duration": result.total_duration_seconds,
            "error": result.error_message
        }
    except Exception as e:
        logger.exception(f"Error processing twin {twin_id}: {e}")
        return {
            "twin_id": twin_id,
            "success": False,
            "error": str(e)
        }


async def backfill_batch(twin_ids: List[str], force: bool = False) -> List[dict]:
    """Process a batch of twins."""
    results = []
    for twin_id in twin_ids:
        result = await backfill_twin(twin_id, force)
        results.append(result)
    return results


async def main():
    parser = argparse.ArgumentParser(description="Backfill Person Completeness v1")
    parser.add_argument("--twin-id", help="Process specific twin")
    parser.add_argument("--all-twins", action="store_true", help="Process all twins")
    parser.add_argument("--needs-backfill", action="store_true", help="Process only twins needing backfill")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if recently processed")

    args = parser.parse_args()

    # Determine which twins to process
    if args.twin_id:
        twin_ids = [args.twin_id]
    elif args.needs_backfill:
        twin_ids = get_twins_needing_backfill()
        logger.info(f"Found {len(twin_ids)} twins needing backfill")
    elif args.all_twins:
        twin_ids = get_all_twin_ids()
        logger.info(f"Found {len(twin_ids)} total twins")
    else:
        logger.error("Must specify --twin-id, --all-twins, or --needs-backfill")
        return

    if not twin_ids:
        logger.info("No twins to process")
        return

    # Process in batches
    results = []
    for i in range(0, len(twin_ids), args.batch_size):
        batch = twin_ids[i:i + args.batch_size]
        logger.info(f"Processing batch {i // args.batch_size + 1}/{(len(twin_ids) + args.batch_size - 1) // args.batch_size}")
        batch_results = await backfill_batch(batch, args.force)
        results.extend(batch_results)

    # Summary
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    logger.info("=" * 50)
    logger.info(f"Backfill complete: {successful} successful, {failed} failed")
    logger.info("=" * 50)

    if failed > 0:
        for r in results:
            if not r.get("success"):
                logger.error(f"Failed: {r['twin_id']} - {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
