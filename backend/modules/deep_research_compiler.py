"""
Deep Research Compiler

Shared compilation logic used by both the router (compile-to-twin endpoint)
and the worker pipeline (auto-compile after research completes).

Public API:
    compile_run_to_twin(*, run_id, twin_id, tenant_id, result, db) -> dict
"""

from __future__ import annotations

import hashlib
import logging
import uuid as _uuid
from typing import Any, Dict, List, Tuple

from modules.public_profile_pack import build_research_profile_projection, merge_materialized_profile_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Claim type mapping: deep research claim_type → persona claim_type
# ---------------------------------------------------------------------------
_DR_CLAIM_TYPE_MAP: Dict[str, str] = {
    "credential": "belief",
    "experience": "experience",
    "role": "belief",
    "preference": "preference",
    "opinion": "belief",
    "project": "experience",
    "contact": "uncertain",
    "other": "uncertain",
}


def _build_deep_research_chunks(result: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convert a deep research result artifact into a flat text document and a
    list of granular chunk entries for per-item Pinecone vector indexing.

    Returns:
        (text_doc, chunk_entries) — text_doc is the full concatenated text for
        the sources table; chunk_entries is passed as chunk_entries_override to
        process_and_index_text so each Q&A pair, claim, and timeline event gets
        its own embedding vector.
    """
    lines: List[str] = []
    chunk_entries: List[Dict[str, Any]] = []

    def _add(text: str) -> None:
        lines.append(text)
        chunk_entries.append({"text": text, "block_type": "answer_text", "is_answer_text": True})

    bio = result.get("bio") or {}
    if bio.get("medium"):
        _add(bio["medium"])

    profile_summary = result.get("profile_summary") or {}
    summary_parts: List[str] = []
    if profile_summary.get("what_they_do"):
        summary_parts.append("What they do: " + "; ".join(profile_summary["what_they_do"]))
    if profile_summary.get("public_roles"):
        summary_parts.append("Public roles: " + ", ".join(profile_summary["public_roles"]))
    if profile_summary.get("organizations"):
        summary_parts.append("Organizations: " + ", ".join(profile_summary["organizations"]))
    if summary_parts:
        _add("\n".join(summary_parts))

    for item in result.get("timeline") or []:
        if item.get("event"):
            _add(f"{item.get('date_or_range', '')}: {item['event']}")

    for claim in result.get("claims") or []:
        if claim.get("text"):
            _add(claim["text"])

    for qa in result.get("prepared_question_answers") or []:
        if qa.get("question") and qa.get("answer"):
            _add(f"Q: {qa['question']}\nA: {qa['answer']}")

    return "\n\n".join(lines).strip(), chunk_entries


async def compile_run_to_twin(
    *,
    run_id: str,
    twin_id: str,
    tenant_id: str,
    result: dict,
    db,
) -> dict:
    """
    Ingest a completed deep research result into the twin's knowledge base.

    Steps:
    1. Delete any prior "Deep Research:" sources for this twin (prevents duplicate vectors).
    2. Build text document + granular chunk list from the result artifact.
    3. Register new source and index to Pinecone with granular chunks.
    4. Map structured claims to PersonaClaim and store them.
    5. Compile persona from stored claims.
    6. Write the bio from the result to the twin's public profile.
    7. Advance twin status to persona_built (unlocks chat).

    Args:
        run_id:    ID of the deep research run.
        twin_id:   Target twin ID.
        tenant_id: Tenant owning the twin.
        result:    The result artifact dict (as stored in name_deep_research_artifacts).
        db:        Supabase client (sync postgrest client from modules.observability).

    Returns:
        dict with keys: status, twin_id, claims_ingested, bio_written, chunks_indexed
    """
    from modules.ingestion import delete_source, process_and_index_text
    from modules.persona_claim_extractor import ClaimCitation, ClaimStore, PersonaClaim
    from modules.persona_claim_inference import PersonaFromClaimsCompiler

    # ------------------------------------------------------------------
    # 1. Build text document + granular chunk list for Pinecone indexing
    # ------------------------------------------------------------------
    text_doc, chunk_entries = _build_deep_research_chunks(result)
    if not text_doc:
        raise ValueError("Deep research result contains no indexable content")

    # ------------------------------------------------------------------
    # 2. Delete any prior deep-research sources for this twin to prevent
    #    duplicate vectors from a repeated compile call.
    # ------------------------------------------------------------------
    try:
        prior_sources = (
            db.table("sources")
            .select("id")
            .eq("twin_id", twin_id)
            .like("filename", "Deep Research:%")
            .execute()
        )
        for prior in prior_sources.data or []:
            try:
                await delete_source(source_id=prior["id"], twin_id=twin_id)
            except Exception as exc:
                logger.warning(
                    "compile_run_to_twin: could not delete prior source %s for twin %s: %s",
                    prior["id"], twin_id, exc,
                )
    except Exception as exc:
        logger.warning(
            "compile_run_to_twin: error querying prior sources for twin %s: %s", twin_id, exc
        )

    # ------------------------------------------------------------------
    # 3. Register new source and index to Pinecone with granular chunks
    # ------------------------------------------------------------------
    input_name = (result.get("input") or {}).get("name", "Profile")
    source_id = str(_uuid.uuid4())
    try:
        db.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"Deep Research: {input_name}"[:240],
            "file_size": len(text_doc),
            "content_text": text_doc,
            "status": "processing",
        }).execute()
    except Exception as exc:
        logger.error(
            "compile_run_to_twin: failed to insert source record twin=%s run=%s: %s",
            twin_id, run_id, exc,
        )
        raise

    try:
        await process_and_index_text(
            source_id=source_id,
            twin_id=twin_id,
            text=text_doc,
            provider="deep_research",
            chunk_entries_override=chunk_entries if chunk_entries else None,
        )
        db.table("sources").update({"status": "live"}).eq("id", source_id).execute()
    except Exception as exc:
        db.table("sources").update({"status": "failed"}).eq("id", source_id).execute()
        logger.error(
            "compile_run_to_twin: indexing failed twin=%s run=%s: %s", twin_id, run_id, exc
        )
        raise

    # ------------------------------------------------------------------
    # 4. Map deep research claims → PersonaClaim and store
    # ------------------------------------------------------------------
    claims_to_store: list = []
    try:
        for item in result.get("claims") or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            claims_to_store.append(PersonaClaim(
                twin_id=twin_id,
                claim_text=text,
                claim_type=_DR_CLAIM_TYPE_MAP.get(item.get("claim_type", "other"), "uncertain"),
                confidence=float(item.get("confidence", 0.7)),
                authority="extracted",
                citation=ClaimCitation(
                    source_id=source_id,
                    chunk_id=f"dr_{item.get('claim_id', '')}",
                    span_start=0,
                    span_end=len(text),
                    quote=text[:120],
                    content_hash=content_hash,
                ),
                extraction_version="dr-1.0",
            ))

        claim_store = ClaimStore(db)
        await claim_store.save_claims(claims_to_store)
        logger.info(
            "compile_run_to_twin: stored %d claims twin=%s run=%s",
            len(claims_to_store), twin_id, run_id,
        )
    except Exception as exc:
        logger.error(
            "compile_run_to_twin: claim storage failed twin=%s run=%s: %s", twin_id, run_id, exc
        )
        raise

    # ------------------------------------------------------------------
    # 5. Compile persona spec from claims, enrich with research identity,
    #    and publish as active — this is what the chat system prompt uses.
    # ------------------------------------------------------------------
    try:
        from modules.persona_spec_store_v2 import create_persona_spec_v2, publish_persona_spec_v2
        from modules.persona_spec_v2 import (
            CommunicationPatterns,
            IdentityFrame,
            PersonaSpecV2,
        )

        compiler = PersonaFromClaimsCompiler(db)
        compile_result = await compiler.compile_persona(twin_id)
        persona_spec: PersonaSpecV2 = compile_result["persona_spec"]

        # Enrich IdentityFrame from research data — this is what produces a
        # specific, grounded persona voice instead of the generic fallback.
        bio = result.get("bio") or {}
        profile_summary = result.get("profile_summary") or {}
        input_name = (result.get("input") or {}).get("name", "") or twin_id

        public_roles = profile_summary.get("public_roles") or []
        role_definition = public_roles[0] if public_roles else input_name
        expertise_raw = profile_summary.get("expertise_topics") or []
        expertise_domains = [
            t.get("topic", t) if isinstance(t, dict) else str(t)
            for t in expertise_raw
        ][:6]
        background_summary = bio.get("medium") or bio.get("short") or ""
        organizations = profile_summary.get("organizations") or []
        what_they_do = profile_summary.get("what_they_do") or []

        # Pull quotes from Q&A pairs as signature phrases — these are the
        # person's actual words from verified web sources.
        signature_phrases: List[str] = []
        for qa in (result.get("prepared_question_answers") or [])[:10]:
            answer = (qa.get("answer") or "").strip()
            if answer and len(answer) < 120:
                signature_phrases.append(answer)
        # Fall back to short bio sentence fragments
        if not signature_phrases and bio.get("short"):
            signature_phrases = [bio["short"][:100]]

        persona_spec.identity_frame = IdentityFrame(
            role_definition=role_definition,
            expertise_domains=expertise_domains,
            background_summary=background_summary,
            reasoning_style="first_principles",
            relationship_to_user="advisor",
            communication_tendencies={
                "directness": "direct",
                "formality": "professional",
                "verbosity": "concise",
                "organizations": ", ".join(organizations[:3]) if organizations else "",
                "what_they_do": "; ".join(what_they_do[:3]) if what_they_do else "",
            },
        )

        # CommunicationPatterns: banned phrases enforce no-AI-tell, signature
        # phrases ground the voice in the person's actual language.
        persona_spec.communication_patterns = CommunicationPatterns(
            signature_phrases=signature_phrases[:5],
            anti_patterns=[
                "Great question!",
                "I'd be happy to help!",
                "Certainly!",
                "Absolutely!",
                "As an AI",
                "as a language model",
                "Let me break this down",
                "Here are some key points:",
                "In conclusion,",
                "It depends.",
            ],
            brevity_preference="concise",
        )

        # Save and publish so agent.py picks it up on the next chat request.
        spec_row = await create_persona_spec_v2(
            twin_id=twin_id,
            tenant_id=tenant_id,
            created_by="system:deep_research_compiler",
            spec=persona_spec,
            status="draft",
            source="deep_research",
            notes=f"Auto-compiled from deep research run {run_id}",
        )
        if spec_row:
            await publish_persona_spec_v2(twin_id=twin_id, version=spec_row["version"])
            logger.info(
                "compile_run_to_twin: persona spec v=%s published twin=%s run=%s",
                spec_row["version"], twin_id, run_id,
            )
        else:
            logger.warning(
                "compile_run_to_twin: persona spec save returned nothing twin=%s run=%s",
                twin_id, run_id,
            )
    except Exception as exc:
        logger.error(
            "compile_run_to_twin: persona compile failed twin=%s run=%s: %s", twin_id, run_id, exc
        )
        raise

    # ------------------------------------------------------------------
    # 6. Publish a clean public profile projection from the research result.
    # ------------------------------------------------------------------
    bio = result.get("bio") or {}
    bio_text = bio.get("short") or bio.get("medium") or ""
    bio_written = False
    if bio_text:
        try:
            twin_row = (
                db.table("twins")
                .select("id, name, description, settings")
                .eq("id", twin_id)
                .single()
                .execute()
            )
            current_twin = twin_row.data or {}
            current_settings = current_twin.get("settings") or {}
            projection = build_research_profile_projection(
                {
                    "id": twin_id,
                    "name": current_twin.get("name"),
                    "description": current_twin.get("description"),
                    "settings": current_settings,
                },
                result,
                source_flow="deep_research_compile",
            )
            merged_settings = merge_materialized_profile_settings(current_settings, projection)
            projection_meta = projection.get("public_profile_meta") or {}
            logger.info(
                "deep_research materialization complete twin=%s run=%s completeness=%s image_status=%s image_source_type=%s",
                twin_id,
                run_id,
                projection_meta.get("completeness_score"),
                projection_meta.get("image_status"),
                projection_meta.get("image_source_type"),
            )
            update_payload = {
                "settings": merged_settings
            }
            if projection.get("description") or current_twin.get("description") or bio_text:
                update_payload["description"] = (
                    projection.get("description") or current_twin.get("description") or bio_text
                )
            if projection.get("specialization"):
                update_payload["specialization"] = projection["specialization"]
            db.table("twins").update(update_payload).eq("id", twin_id).execute()
            bio_written = True
        except Exception as exc:
            logger.warning(
                "compile_run_to_twin: bio write failed twin=%s run=%s: %s", twin_id, run_id, exc
            )

    # ------------------------------------------------------------------
    # 7. Advance status to persona_built (unlocks chat gate)
    # ------------------------------------------------------------------
    try:
        db.table("twins").update({"status": "persona_built"}).eq("id", twin_id).execute()
        logger.info(
            "compile_run_to_twin: twin status -> persona_built twin=%s run=%s", twin_id, run_id
        )
    except Exception as exc:
        logger.error(
            "compile_run_to_twin: status update failed twin=%s run=%s: %s", twin_id, run_id, exc
        )
        raise

    return {
        "status": "completed",
        "twin_id": twin_id,
        "claims_ingested": len(claims_to_store),
        "bio_written": bio_written,
        "chunks_indexed": len(chunk_entries),
    }
