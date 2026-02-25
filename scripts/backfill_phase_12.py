#!/usr/bin/env python3
"""
Phase 12 Backfill Script

Backfills runtime publication for historical research runs.

Usage:
    # Dry run to preview
    python scripts/backfill_phase_12.py --dry-run
    
    # Backfill specific twin
    python scripts/backfill_phase_12.py --twin-id <twin-id>
    
    # Backfill specific runs
    python scripts/backfill_phase_12.py --run-ids run-1 run-2 run-3
    
    # Backfill with specific batch size
    python scripts/backfill_phase_12.py --batch-size 50
    
    # Resume from previous run
    python scripts/backfill_phase_12.py --resume-token <token>
"""

import os
import sys
import asyncio
import argparse
from typing import List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.modules.research_claim_runtime_service import (
    ResearchClaimRuntimeService,
    BackfillResult,
)


def print_progress(msg: str):
    """Print progress message with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def print_success(msg: str):
    """Print success message."""
    print(f"\033[92m✓\033[0m {msg}")


def print_error(msg: str):
    """Print error message."""
    print(f"\033[91m✗\033[0m {msg}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"\033[93m⚠\033[0m {msg}")


async def run_backfill(
    twin_id: Optional[str] = None,
    run_ids: Optional[List[str]] = None,
    dry_run: bool = False,
    batch_size: int = 100,
    resume_token: Optional[str] = None,
) -> BackfillResult:
    """Run the backfill operation."""
    service = ResearchClaimRuntimeService()
    
    print_progress("Starting Phase 12 backfill...")
    print_progress(f"  Dry run: {dry_run}")
    print_progress(f"  Batch size: {batch_size}")
    
    if twin_id:
        print_progress(f"  Twin ID: {twin_id}")
    if run_ids:
        print_progress(f"  Specific runs: {len(run_ids)} runs")
    if resume_token:
        print_progress(f"  Resume token: {resume_token}")
    
    print()
    
    result = await service.backfill_publication(
        twin_id=twin_id,
        research_run_ids=run_ids,
        dry_run=dry_run,
        batch_size=batch_size,
        resume_token=resume_token,
    )
    
    return result


def print_results(result: BackfillResult):
    """Print backfill results."""
    print("\n" + "="*60)
    print("BACKFILL RESULTS")
    print("="*60)
    
    if result.success:
        print_success("Backfill completed successfully")
    else:
        print_error("Backfill failed")
    
    print(f"\nTotal runs: {result.total_runs}")
    print(f"Processed: {result.processed_runs}")
    print(f"Failed: {result.failed_runs}")
    print(f"\nTotal claims: {result.total_claims}")
    print(f"Published: {result.published_count}")
    print(f"Suppressed: {result.suppressed_count}")
    
    if result.resume_token:
        print(f"\nResume token: {result.resume_token}")
        print_warning("More runs available - re-run with --resume-token to continue")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for i, error in enumerate(result.errors[:10], 1):
            print_error(f"  {i}. {error}")
        if len(result.errors) > 10:
            print_warning(f"  ... and {len(result.errors) - 10} more")
    
    print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Phase 12 Runtime Publication Backfill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview
  python scripts/backfill_phase_12.py --dry-run
  
  # Backfill specific twin
  python scripts/backfill_phase_12.py --twin-id abc-123
  
  # Backfill specific runs
  python scripts/backfill_phase_12.py --run-ids run-1 run-2 run-3
  
  # Resume from previous run
  python scripts/backfill_phase_12.py --resume-token last-run-id
        """
    )
    
    parser.add_argument(
        "--twin-id",
        help="Limit backfill to specific twin"
    )
    
    parser.add_argument(
        "--run-ids",
        nargs="+",
        help="Specific research run IDs to backfill"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without actually publishing"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of runs to process per batch (default: 100)"
    )
    
    parser.add_argument(
        "--resume-token",
        help="Resume from previous run (last processed run ID)"
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    # Print header
    print("="*60)
    print("PHASE 12 RUNTIME PUBLICATION BACKFILL")
    print("="*60)
    print(f"Time: {datetime.now().isoformat()}")
    print("="*60)
    
    # Check environment
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        print_error("Missing required environment variables:")
        print("  - SUPABASE_URL")
        print("  - SUPABASE_SERVICE_KEY")
        sys.exit(1)
    
    # Confirmation
    if not args.dry_run and not args.yes:
        print_warning("This will publish claims to the runtime layer!")
        response = input("Continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)
    
    # Run backfill
    result = asyncio.run(run_backfill(
        twin_id=args.twin_id,
        run_ids=args.run_ids,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        resume_token=args.resume_token,
    ))
    
    # Print results
    print_results(result)
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
