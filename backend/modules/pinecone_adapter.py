import logging
import os
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

ALLOWED_INDEX_MODES = {"vector", "integrated"}
DEFAULT_INDEX_MODE = "vector"
DEFAULT_TEXT_FIELD = "chunk_text"
DEFAULT_METADATA_FIELDS = [
    "text",
    "source_id",
    "twin_id",
    "chunk_id",
    "doc_id",
    "filename",
    "doc_name",
    "page_number",
    "is_verified",
    "category",
    "tone",
    "opinion_topic",
    "opinion_stance",
    "opinion_intensity",
    "chunk_type",
    "block_type",
    "is_answer_text",
    "section_title",
    "section_path",
    "creator_id",
    "synthetic_questions",
    "author",
    "publish_date",
    "citation_url",
    "url",
    "type",
]


def get_pinecone_index_mode() -> str:
    raw_mode = (os.getenv("PINECONE_INDEX_MODE", DEFAULT_INDEX_MODE) or "").strip().lower()
    if raw_mode in ALLOWED_INDEX_MODES:
        return raw_mode
    logger.warning(
        "[PineconeAdapter] Invalid PINECONE_INDEX_MODE='%s'; defaulting to '%s'",
        raw_mode,
        DEFAULT_INDEX_MODE,
    )
    return DEFAULT_INDEX_MODE


def get_pinecone_text_field() -> str:
    return (os.getenv("PINECONE_TEXT_FIELD", DEFAULT_TEXT_FIELD) or "").strip()


class PineconeIndexAdapter:
    """
    Small compatibility layer for Pinecone data-plane operations.

    - vector mode: index.upsert / index.query
    - integrated mode: index.upsert_records / index.search_records
    """

    def __init__(self, index: Any):
        self.index = index
        self.mode = get_pinecone_index_mode()
        self.text_field = get_pinecone_text_field()
        self.host_override = bool((os.getenv("PINECONE_HOST") or "").strip())

        logger.info(
            "[PineconeAdapter] Initialized mode=%s host_override=%s",
            self.mode,
            self.host_override,
        )

        if self.mode == "integrated":
            if not self.text_field:
                raise ValueError(
                    "PINECONE_TEXT_FIELD is required when PINECONE_INDEX_MODE=integrated"
                )
            if not hasattr(self.index, "upsert_records") or not hasattr(self.index, "search_records"):
                raise ValueError(
                    "Pinecone index client does not support integrated mode "
                    "(requires upsert_records/search_records)"
                )

    def upsert(self, vectors: List[Dict[str, Any]], namespace: str) -> Any:
        if self.mode == "vector":
            return self.index.upsert(vectors=vectors, namespace=namespace)

        records: List[Dict[str, Any]] = []
        for vector in vectors:
            metadata = dict(vector.get("metadata") or {})
            text_value = str(metadata.get("text") or "").strip()
            if not text_value:
                continue

            record_id = str(vector.get("id") or "").strip()
            if not record_id:
                continue

            record: Dict[str, Any] = {"_id": record_id}
            record.update(metadata)
            # Ensure the configured embedding field is populated for integrated indexes.
            record[self.text_field] = text_value
            records.append(record)

        if not records:
            return {"upserted_count": 0}
        return self.index.upsert_records(namespace=namespace, records=records)

    def query(
        self,
        *,
        vector: Optional[List[float]],
        query_text: Optional[str],
        top_k: int,
        namespace: str,
        include_metadata: bool = True,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.mode == "vector":
            params: Dict[str, Any] = {
                "vector": vector,
                "top_k": top_k,
                "include_metadata": include_metadata,
                "namespace": namespace,
            }
            if metadata_filter:
                params["filter"] = metadata_filter
            return self.index.query(**params)

        cleaned_query = (query_text or "").strip()
        if not cleaned_query:
            raise ValueError(
                "query_text is required when PINECONE_INDEX_MODE=integrated"
            )

        payload: Dict[str, Any] = {
            "inputs": {"text": cleaned_query},
            "top_k": top_k,
        }
        if metadata_filter:
            payload["filter"] = metadata_filter

        response = self.index.search_records(
            namespace=namespace,
            query=payload,
            fields=self._integrated_fields(),
        )
        return self._normalize_search_records_response(response)

    def _integrated_fields(self) -> List[str]:
        fields = [self.text_field]
        for field in DEFAULT_METADATA_FIELDS:
            if field not in fields:
                fields.append(field)
        return fields

    def _normalize_search_records_response(self, response: Any) -> Dict[str, Any]:
        hits: List[Any] = []
        if isinstance(response, dict):
            result = response.get("result") or {}
            hits = result.get("hits") or response.get("hits") or []
        else:
            result = getattr(response, "result", None)
            hits = getattr(result, "hits", None) if result is not None else None
            if hits is None:
                hits = getattr(response, "hits", []) or []

        normalized: List[Dict[str, Any]] = []
        for hit in hits or []:
            if isinstance(hit, dict):
                hit_id = hit.get("_id") or hit.get("id")
                score = hit.get("_score", hit.get("score", 0.0))
                fields = dict(hit.get("fields") or {})
            else:
                hit_id = getattr(hit, "_id", None) or getattr(hit, "id", None)
                score = getattr(hit, "_score", getattr(hit, "score", 0.0))
                fields = dict(getattr(hit, "fields", {}) or {})

            if self.text_field in fields and "text" not in fields:
                fields["text"] = fields[self.text_field]

            normalized.append(
                {
                    "id": hit_id,
                    "score": float(score or 0.0),
                    "metadata": fields,
                }
            )

        return {"matches": normalized}
