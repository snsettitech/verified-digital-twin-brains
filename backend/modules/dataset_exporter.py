# backend/modules/dataset_exporter.py
"""Dataset Exporter for Fine-Tuning

Exports datasets in various formats for model training.
"""

import os
import json
import csv
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    JSONL = "jsonl"
    CSV = "csv"
    OPENAI = "openai"  # OpenAI fine-tuning format
    HUGGINGFACE = "huggingface"  # HuggingFace datasets format


class DatasetExporter:
    """Exports Langfuse datasets for model training."""
    
    def __init__(self):
        self._langfuse_available = False
        self._init_langfuse()
    
    def _init_langfuse(self):
        """Initialize Langfuse client."""
        try:
            from langfuse import Langfuse
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if public_key and secret_key:
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._langfuse_available = True
                logger.info("Dataset Exporter initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for export: {e}")
    
    async def export_dataset(
        self,
        dataset_name: str,
        output_path: str,
        format: ExportFormat = ExportFormat.JSONL,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        query_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        train_split: float = 0.8,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Export a dataset to a file.
        
        Args:
            dataset_name: Name of the Langfuse dataset
            output_path: Path to save the exported file
            format: Export format
            min_score: Filter by minimum score
            max_score: Filter by maximum score
            query_type: Filter by query type
            from_date: Filter by date range start
            to_date: Filter by date range end
            train_split: Training set percentage (0-1)
            seed: Random seed for train/val split
        
        Returns:
            Export statistics
        """
        if not self._langfuse_available:
            raise RuntimeError("Langfuse not available for export")
        
        # Load dataset
        dataset = self._client.get_dataset(dataset_name)
        items = list(dataset.items)
        
        # Filter items
        filtered_items = self._filter_items(
            items,
            min_score=min_score,
            max_score=max_score,
            query_type=query_type,
            from_date=from_date,
            to_date=to_date
        )
        
        logger.info(f"Exporting {len(filtered_items)} items from {dataset_name}")
        
        # Split train/val
        import random
        random.seed(seed)
        random.shuffle(filtered_items)
        
        split_idx = int(len(filtered_items) * train_split)
        train_items = filtered_items[:split_idx]
        val_items = filtered_items[split_idx:]
        
        # Export based on format
        if format == ExportFormat.JSONL:
            self._export_jsonl(train_items, val_items, output_path)
        elif format == ExportFormat.CSV:
            self._export_csv(train_items, val_items, output_path)
        elif format == ExportFormat.OPENAI:
            self._export_openai(train_items, val_items, output_path)
        elif format == ExportFormat.HUGGINGFACE:
            self._export_huggingface(train_items, val_items, output_path)
        
        # Generate stats
        stats = self._generate_stats(filtered_items, train_items, val_items)
        
        # Save stats
        stats_path = str(Path(output_path).with_suffix('.stats.json'))
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Export complete: {output_path}")
        return stats
    
    def _filter_items(
        self,
        items: List[Any],
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        query_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Any]:
        """Filter dataset items based on criteria."""
        filtered = items
        
        if min_score is not None or max_score is not None:
            filtered = [
                item for item in filtered
                if self._score_in_range(item, min_score, max_score)
            ]
        
        if query_type:
            filtered = [
                item for item in filtered
                if (item.metadata or {}).get("query_type") == query_type
            ]
        
        if from_date or to_date:
            filtered = [
                item for item in filtered
                if self._date_in_range(item, from_date, to_date)
            ]
        
        return filtered
    
    def _score_in_range(
        self,
        item: Any,
        min_score: Optional[float],
        max_score: Optional[float]
    ) -> bool:
        """Check if item score is in range."""
        score = (item.metadata or {}).get("overall_score", 0.8)
        
        if min_score is not None and score < min_score:
            return False
        if max_score is not None and score > max_score:
            return False
        return True
    
    def _date_in_range(
        self,
        item: Any,
        from_date: Optional[datetime],
        to_date: Optional[datetime]
    ) -> bool:
        """Check if item date is in range."""
        date_str = (item.metadata or {}).get("collected_at")
        if not date_str:
            return True
        
        try:
            item_date = datetime.fromisoformat(date_str)
            if from_date and item_date < from_date:
                return False
            if to_date and item_date > to_date:
                return False
            return True
        except (TypeError, ValueError):
            return True
    
    def _export_jsonl(
        self,
        train_items: List[Any],
        val_items: List[Any],
        output_path: str
    ):
        """Export in JSONL format."""
        base_path = Path(output_path)
        
        # Train file
        train_path = base_path.with_suffix('.train.jsonl')
        with open(train_path, 'w', encoding='utf-8') as f:
            for item in train_items:
                record = {
                    "input": item.input,
                    "output": item.expected_output,
                    "metadata": item.metadata
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        # Val file
        val_path = base_path.with_suffix('.val.jsonl')
        with open(val_path, 'w', encoding='utf-8') as f:
            for item in val_items:
                record = {
                    "input": item.input,
                    "output": item.expected_output,
                    "metadata": item.metadata
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def _export_csv(
        self,
        train_items: List[Any],
        val_items: List[Any],
        output_path: str
    ):
        """Export in CSV format."""
        base_path = Path(output_path)
        
        # Train file
        train_path = base_path.with_suffix('.train.csv')
        with open(train_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['query', 'response', 'score', 'query_type'])
            for item in train_items:
                writer.writerow([
                    item.input.get('query', ''),
                    item.expected_output.get('response', ''),
                    (item.metadata or {}).get('overall_score', ''),
                    (item.metadata or {}).get('query_type', '')
                ])
        
        # Val file
        val_path = base_path.with_suffix('.val.csv')
        with open(val_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['query', 'response', 'score', 'query_type'])
            for item in val_items:
                writer.writerow([
                    item.input.get('query', ''),
                    item.expected_output.get('response', ''),
                    (item.metadata or {}).get('overall_score', ''),
                    (item.metadata or {}).get('query_type', '')
                ])
    
    def _export_openai(
        self,
        train_items: List[Any],
        val_items: List[Any],
        output_path: str
    ):
        """Export in OpenAI fine-tuning format."""
        base_path = Path(output_path)
        system_msg = "You are a helpful digital twin assistant."
        
        # Train file
        train_path = base_path.with_suffix('.train.jsonl')
        with open(train_path, 'w', encoding='utf-8') as f:
            for item in train_items:
                record = {
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": item.input.get('query', '')},
                        {"role": "assistant", "content": item.expected_output.get('response', '')}
                    ]
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        # Val file
        val_path = base_path.with_suffix('.val.jsonl')
        with open(val_path, 'w', encoding='utf-8') as f:
            for item in val_items:
                record = {
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": item.input.get('query', '')},
                        {"role": "assistant", "content": item.expected_output.get('response', '')}
                    ]
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def _export_huggingface(
        self,
        train_items: List[Any],
        val_items: List[Any],
        output_path: str
    ):
        """Export in HuggingFace datasets format."""
        # Creates a directory with train.jsonl and validation.jsonl
        base_path = Path(output_path)
        output_dir = base_path.parent / base_path.stem
        output_dir.mkdir(exist_ok=True)
        
        # Train file
        with open(output_dir / 'train.jsonl', 'w', encoding='utf-8') as f:
            for item in train_items:
                record = {
                    "instruction": "Answer based on the owner's knowledge.",
                    "input": item.input.get('query', ''),
                    "output": item.expected_output.get('response', ''),
                    "context": item.input.get('context', '')[:1000]
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        # Validation file
        with open(output_dir / 'validation.jsonl', 'w', encoding='utf-8') as f:
            for item in val_items:
                record = {
                    "instruction": "Answer based on the owner's knowledge.",
                    "input": item.input.get('query', ''),
                    "output": item.expected_output.get('response', ''),
                    "context": item.input.get('context', '')[:1000]
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def _generate_stats(
        self,
        all_items: List[Any],
        train_items: List[Any],
        val_items: List[Any]
    ) -> Dict[str, Any]:
        """Generate export statistics."""
        scores = [(item.metadata or {}).get("overall_score", 0.8) for item in all_items]
        
        query_types = {}
        for item in all_items:
            qt = (item.metadata or {}).get("query_type", "unknown")
            query_types[qt] = query_types.get(qt, 0) + 1
        
        return {
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_items": len(all_items),
            "train_items": len(train_items),
            "val_items": len(val_items),
            "train_split": round(len(train_items) / len(all_items), 2) if all_items else 0,
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0,
            "min_score": round(min(scores), 3) if scores else 0,
            "max_score": round(max(scores), 3) if scores else 0,
            "query_types": query_types
        }


# Singleton instance
_exporter: Optional[DatasetExporter] = None


def get_dataset_exporter() -> DatasetExporter:
    """Get or create the singleton exporter."""
    global _exporter
    if _exporter is None:
        _exporter = DatasetExporter()
    return _exporter
