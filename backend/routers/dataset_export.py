# backend/routers/dataset_export.py
"""Dataset Export API Endpoints

Export datasets for fine-tuning and analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime
import logging

from modules.auth_guard import require_admin
from modules.dataset_exporter import (
    DatasetExporter,
    ExportFormat,
    get_dataset_exporter
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/datasets", tags=["dataset-export"])


@router.post("/{dataset_name}/export")
async def export_dataset(
    dataset_name: str,
    output_path: str,
    format: str = "jsonl",
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    query_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    train_split: float = 0.8,
    background: bool = False,
    background_tasks: BackgroundTasks = None,
    user=Depends(require_admin)
):
    """
    Export a dataset to a file.
    
    Args:
        dataset_name: Name of the Langfuse dataset
        output_path: Path to save the exported file
        format: Export format (jsonl, csv, openai, huggingface)
        min_score: Filter by minimum score
        max_score: Filter by maximum score
        query_type: Filter by query type
        from_date: Filter by date range start
        to_date: Filter by date range end
        train_split: Training set percentage (0-1)
        background: Run in background
    
    Returns:
        Export statistics or job status
    """
    try:
        exporter = get_dataset_exporter()
        export_format = ExportFormat(format)
        
        if background and background_tasks:
            # Run in background
            async def do_export():
                try:
                    stats = await exporter.export_dataset(
                        dataset_name=dataset_name,
                        output_path=output_path,
                        format=export_format,
                        min_score=min_score,
                        max_score=max_score,
                        query_type=query_type,
                        from_date=from_date,
                        to_date=to_date,
                        train_split=train_split
                    )
                    logger.info(f"Dataset export complete: {output_path}")
                except Exception as e:
                    logger.error(f"Dataset export failed: {e}")
            
            background_tasks.add_task(do_export)
            
            return {
                "status": "started",
                "message": "Export started in background",
                "dataset_name": dataset_name,
                "output_path": output_path
            }
        else:
            # Run synchronously
            stats = await exporter.export_dataset(
                dataset_name=dataset_name,
                output_path=output_path,
                format=export_format,
                min_score=min_score,
                max_score=max_score,
                query_type=query_type,
                from_date=from_date,
                to_date=to_date,
                train_split=train_split
            )
            
            return {
                "status": "complete",
                "dataset_name": dataset_name,
                "output_path": output_path,
                "stats": stats
            }
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid format: {e}")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/formats")
async def get_export_formats(
    user=Depends(require_admin)
):
    """Get available export formats."""
    return [
        {"format": "jsonl", "description": "JSON Lines format with metadata"},
        {"format": "csv", "description": "CSV format for spreadsheet analysis"},
        {"format": "openai", "description": "OpenAI fine-tuning format (messages)"},
        {"format": "huggingface", "description": "HuggingFace datasets format (instruction/input/output)"}
    ]


@router.get("/{dataset_name}/stats")
async def get_dataset_export_stats(
    dataset_name: str,
    user=Depends(require_admin)
):
    """Get dataset statistics for export planning."""
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        dataset = client.get_dataset(dataset_name)
        items = list(dataset.items)
        
        if not items:
            return {
                "dataset_name": dataset_name,
                "item_count": 0,
                "message": "Dataset is empty"
            }
        
        # Calculate stats
        scores = []
        query_types = {}
        date_range = {"min": None, "max": None}
        
        for item in items:
            # Score
            score = (item.metadata or {}).get("overall_score", 0.8)
            scores.append(score)
            
            # Query type
            qt = (item.metadata or {}).get("query_type", "unknown")
            query_types[qt] = query_types.get(qt, 0) + 1
            
            # Date
            date_str = (item.metadata or {}).get("collected_at")
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str)
                    if date_range["min"] is None or dt < date_range["min"]:
                        date_range["min"] = dt
                    if date_range["max"] is None or dt > date_range["max"]:
                        date_range["max"] = dt
                except:
                    pass
        
        return {
            "dataset_name": dataset_name,
            "item_count": len(items),
            "avg_score": round(sum(scores) / len(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "query_types": query_types,
            "date_range": {
                "from": date_range["min"].isoformat() if date_range["min"] else None,
                "to": date_range["max"].isoformat() if date_range["max"] else None
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get dataset stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
