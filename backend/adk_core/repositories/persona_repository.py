"""Persistence for authoritative persona artifacts and quote packs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from adk_core.repositories.base import utc_now_iso
from modules.clients import get_pinecone_index
from modules.embeddings import get_embedding
from modules.observability import supabase


class PersonaRepository:
    """Stores canonical persona artifacts and supporting quote records."""

    def get_active_artifact(
        self,
        *,
        twin_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        query = (
            supabase.table("adk_persona_artifacts")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
        )
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.execute()
        return (response.data or [None])[0]

    def list_quotes(
        self,
        *,
        twin_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table("adk_persona_quotes")
            .select("*")
            .eq("twin_id", twin_id)
            .order("confidence", desc=True)
        )
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.execute()
        return response.data or []

    def publish_artifact(
        self,
        *,
        tenant_id: str,
        twin_id: str,
        artifact: Dict[str, Any],
        publish: bool = True,
    ) -> Dict[str, Any]:
        if publish:
            (
                supabase.table("adk_persona_artifacts")
                .update({"status": "archived", "updated_at": utc_now_iso()})
                .eq("tenant_id", tenant_id)
                .eq("twin_id", twin_id)
                .eq("status", "active")
                .execute()
            )

        payload = {
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "version": artifact["version"],
            "status": "active" if publish else "draft",
            "artifact_json": artifact,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        response = supabase.table("adk_persona_artifacts").insert(payload).execute()
        row = (response.data or [None])[0]
        artifact_id = row["id"]

        (
            supabase.table("adk_persona_quotes")
            .delete()
            .eq("tenant_id", tenant_id)
            .eq("twin_id", twin_id)
            .execute()
        )

        quotes = []
        for idx, item in enumerate(artifact.get("quote_pack") or [], start=1):
            quotes.append(
                {
                    "tenant_id": tenant_id,
                    "twin_id": twin_id,
                    "persona_artifact_id": artifact_id,
                    "quote_text": item.get("quote", ""),
                    "source_id": item.get("source_id"),
                    "context": item.get("context", ""),
                    "confidence": item.get("confidence", 0.0),
                    "position": idx,
                    "created_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                }
            )
        if quotes:
            supabase.table("adk_persona_quotes").insert(quotes).execute()

        self._mirror_to_legacy_twin_settings(twin_id=twin_id, artifact=artifact)
        self._index_for_retrieval(twin_id=twin_id, artifact=artifact, artifact_id=artifact_id)
        return row

    def _mirror_to_legacy_twin_settings(self, *, twin_id: str, artifact: Dict[str, Any]) -> None:
        twin_result = (
            supabase.table("twins")
            .select("settings")
            .eq("id", twin_id)
            .maybe_single()
            .execute()
        )
        current_settings = dict((twin_result.data or {}).get("settings") or {})
        current_settings["public_profile"] = artifact.get("public_profile") or {}
        current_settings["persona_identity_pack"] = artifact.get("persona_identity_pack") or {}
        current_settings["adk_persona_version"] = artifact.get("version")
        (
            supabase.table("twins")
            .update({"settings": current_settings, "status": "persona_built"})
            .eq("id", twin_id)
            .execute()
        )

    def _index_for_retrieval(self, *, twin_id: str, artifact: Dict[str, Any], artifact_id: str) -> None:
        try:
            index = get_pinecone_index()
        except Exception:
            index = None
        if index is None:
            return

        namespace = f"adk-persona-{twin_id}"
        records: List[Dict[str, Any]] = []

        for idx, claim in enumerate(artifact.get("claims") or [], start=1):
            text = str(claim.get("text") or "").strip()
            if not text:
                continue
            records.append(
                {
                    "id": f"{artifact_id}-claim-{idx}",
                    "values": get_embedding(text),
                    "metadata": {
                        "twin_id": twin_id,
                        "artifact_id": artifact_id,
                        "doc_type": "claim",
                        "text": text,
                        "source_ids": claim.get("source_ids") or [],
                    },
                }
            )

        for idx, quote in enumerate(artifact.get("quote_pack") or [], start=1):
            text = str(quote.get("quote") or "").strip()
            if not text:
                continue
            records.append(
                {
                    "id": f"{artifact_id}-quote-{idx}",
                    "values": get_embedding(text),
                    "metadata": {
                        "twin_id": twin_id,
                        "artifact_id": artifact_id,
                        "doc_type": "quote",
                        "text": text,
                        "source_id": quote.get("source_id"),
                    },
                }
            )

        if records:
            index.upsert(vectors=records, namespace=namespace)
