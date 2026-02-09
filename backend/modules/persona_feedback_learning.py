"""
Persona Feedback Learning

Closed-loop behavior shaping:
- ingest user feedback signals into `persona_training_events`
- aggregate feedback + judge outcomes into module confidence updates
- run regression gate before optional auto-publish
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eval.persona_regression_runner import run_persona_regression
from modules.observability import supabase
from modules.persona_intents import normalize_intent_label
from modules.persona_spec_store import publish_persona_spec


NEGATIVE_REASONS = {"incorrect", "hallucination", "off_topic", "incomplete"}
POSITIVE_REASONS = {"great_answer", "helpful"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def record_feedback_training_event(
    *,
    trace_id: str,
    score: float,
    reason: str,
    comment: Optional[str],
    twin_id: Optional[str],
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    message_id: Optional[str],
    intent_label: Optional[str],
    module_ids: Optional[List[str]],
    interaction_context: Optional[str],
    created_by: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Writes a normalized feedback event so learning runs can process it later.
    """
    if not twin_id:
        return None

    event_type = "thumb_up" if score > 0 else "thumb_down"
    payload = {
        "intent_label": normalize_intent_label(intent_label) if intent_label else None,
        "module_ids": [str(mid).strip() for mid in (module_ids or []) if str(mid).strip()],
        "interaction_context": interaction_context,
        "comment": comment,
    }
    insert_payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "trace_id": trace_id,
        "source": "langfuse_feedback",
        "event_type": event_type,
        "score": round(float(score), 4),
        "reason": reason,
        "payload": payload,
        "processed": False,
        "created_by": created_by,
        "updated_at": _now_iso(),
    }
    try:
        res = supabase.table("persona_training_events").insert(insert_payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaFeedbackLearning] feedback event insert failed: {e}")
        return None


def list_feedback_learning_runs(*, twin_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_feedback_learning_runs")
            .select("*")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaFeedbackLearning] list runs failed: {e}")
        return []


def _reason_weight(*, score: float, reason: Optional[str], event_type: Optional[str]) -> float:
    r = (reason or "").strip().lower()
    base = 0.0
    if event_type == "thumb_up":
        base += 0.035
    elif event_type == "thumb_down":
        base -= 0.055

    if r in POSITIVE_REASONS:
        base += 0.02
    if r in NEGATIVE_REASONS:
        base -= 0.03

    if score > 0:
        base += 0.02 * min(score, 1.0)
    elif score < 0:
        base -= 0.03 * min(abs(score), 1.0)

    return _clamp(base, -0.10, 0.08)


def _start_learning_run(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
) -> Optional[Dict[str, Any]]:
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "status": "running",
        "publish_decision": "held",
        "created_by": created_by,
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        res = supabase.table("persona_feedback_learning_runs").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaFeedbackLearning] start run failed: {e}")
        return None


def _finalize_learning_run(*, run_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    update_payload = {
        **payload,
        "completed_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        res = supabase.table("persona_feedback_learning_runs").update(update_payload).eq("id", run_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaFeedbackLearning] finalize run failed: {e}")
        return None


def _fetch_unprocessed_events(*, twin_id: str, limit: int) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_training_events")
            .select("*")
            .eq("twin_id", twin_id)
            .eq("processed", False)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaFeedbackLearning] fetch events failed: {e}")
        return []


def _fetch_recent_judge_results(*, twin_id: str, limit: int) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_judge_results")
            .select(
                "intent_label,module_ids,rewrite_applied,final_persona_score,draft_persona_score,violated_clause_ids"
            )
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaFeedbackLearning] fetch judge results failed: {e}")
        return []


def _fetch_modules(*, twin_id: str) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("persona_modules")
            .select("id,module_id,intent_label,status,confidence,module_data")
            .eq("twin_id", twin_id)
            .in_("status", ["draft", "active"])
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[PersonaFeedbackLearning] fetch modules failed: {e}")
        return []


def _aggregate_signals(
    *,
    events: List[Dict[str, Any]],
    judge_rows: List[Dict[str, Any]],
) -> Tuple[float, Dict[str, float], Dict[str, float], List[str]]:
    global_signal = 0.0
    intent_signal: Dict[str, float] = {}
    module_signal: Dict[str, float] = {}
    processed_event_ids: List[str] = []

    for event in events:
        event_id = event.get("id")
        if event_id:
            processed_event_ids.append(str(event_id))

        weight = _reason_weight(
            score=_to_float(event.get("score")),
            reason=str(event.get("reason") or ""),
            event_type=str(event.get("event_type") or ""),
        )
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        intent_label = payload.get("intent_label")
        if intent_label:
            normalized = normalize_intent_label(str(intent_label))
            intent_signal[normalized] = intent_signal.get(normalized, 0.0) + weight
        else:
            global_signal += weight

        module_ids = payload.get("module_ids") if isinstance(payload.get("module_ids"), list) else []
        for module_id in module_ids:
            normalized_module = str(module_id).strip()
            if not normalized_module:
                continue
            module_signal[normalized_module] = module_signal.get(normalized_module, 0.0) + (weight * 1.10)

    # Fold in recent online-audit quality signals.
    for row in judge_rows:
        intent = normalize_intent_label(str(row.get("intent_label") or "meta_or_system"))
        final_score = _to_float(row.get("final_persona_score"), 1.0)
        rewrite_applied = bool(row.get("rewrite_applied"))
        violated_count = len(row.get("violated_clause_ids") or [])

        if rewrite_applied:
            delta = -0.025
        elif final_score >= 0.92:
            delta = 0.008
        else:
            delta = -0.008
        delta -= min(0.02, violated_count * 0.004)

        intent_signal[intent] = intent_signal.get(intent, 0.0) + delta
        for module_id in row.get("module_ids") or []:
            normalized_module = str(module_id).strip()
            if not normalized_module:
                continue
            module_signal[normalized_module] = module_signal.get(normalized_module, 0.0) + (delta * 1.15)

    return global_signal, intent_signal, module_signal, processed_event_ids


def _update_modules_with_signals(
    *,
    modules: List[Dict[str, Any]],
    global_signal: float,
    intent_signal: Dict[str, float],
    module_signal: Dict[str, float],
    max_confidence_delta: float,
    activation_threshold: float,
    archive_threshold: float,
    run_id: Optional[str],
) -> Dict[str, Any]:
    updates: List[Dict[str, Any]] = []
    deltas: List[float] = []

    for row in modules:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue

        intent = normalize_intent_label(str(row.get("intent_label") or "meta_or_system"))
        current_conf = _to_float(row.get("confidence"), 0.70)
        current_status = str(row.get("status") or "draft")

        raw_delta = (
            global_signal
            + intent_signal.get(intent, 0.0)
            + module_signal.get(module_id, 0.0)
        )
        delta = _clamp(raw_delta, -abs(max_confidence_delta), abs(max_confidence_delta))
        if abs(delta) < 0.0005:
            continue

        next_conf = round(_clamp(current_conf + delta, 0.05, 0.99), 4)
        next_status = current_status
        if next_conf >= activation_threshold:
            next_status = "active"
        elif next_conf < archive_threshold:
            next_status = "archived"

        module_data = row.get("module_data") if isinstance(row.get("module_data"), dict) else {}
        feedback_meta = module_data.get("feedback_learning") if isinstance(module_data.get("feedback_learning"), dict) else {}
        feedback_meta.update(
            {
                "last_run_id": run_id,
                "delta": round(delta, 6),
                "updated_at": _now_iso(),
            }
        )
        module_data["feedback_learning"] = feedback_meta

        payload = {
            "confidence": next_conf,
            "status": next_status,
            "module_data": module_data,
            "updated_at": _now_iso(),
        }
        try:
            supabase.table("persona_modules").update(payload).eq("id", row["id"]).execute()
            deltas.append(delta)
            updates.append(
                {
                    "module_id": module_id,
                    "intent_label": intent,
                    "previous_confidence": round(current_conf, 4),
                    "new_confidence": next_conf,
                    "delta": round(delta, 6),
                    "previous_status": current_status,
                    "new_status": next_status,
                }
            )
        except Exception as e:
            print(f"[PersonaFeedbackLearning] module update failed for {module_id}: {e}")

    return {
        "updates": updates,
        "modules_updated": len(updates),
        "avg_confidence_delta": round(sum(deltas) / len(deltas), 6) if deltas else 0.0,
    }


def _mark_events_processed(event_ids: List[str]) -> int:
    if not event_ids:
        return 0
    try:
        res = (
            supabase.table("persona_training_events")
            .update({"processed": True, "processed_at": _now_iso(), "updated_at": _now_iso()})
            .in_("id", event_ids)
            .execute()
        )
        return len(res.data or [])
    except Exception as e:
        print(f"[PersonaFeedbackLearning] mark processed failed: {e}")
        return 0


def _latest_draft_spec_version(twin_id: str) -> Optional[str]:
    try:
        res = (
            supabase.table("persona_specs")
            .select("version")
            .eq("twin_id", twin_id)
            .eq("status", "draft")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return str(res.data[0].get("version") or "")
    except Exception as e:
        print(f"[PersonaFeedbackLearning] latest draft spec lookup failed: {e}")
    return None


def run_feedback_learning_cycle(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    created_by: Optional[str],
    min_events: int = 10,
    event_limit: int = 500,
    judge_limit: int = 500,
    max_confidence_delta: float = 0.08,
    activation_threshold: float = 0.75,
    archive_threshold: float = 0.45,
    auto_publish: bool = False,
    run_regression_gate: bool = True,
    regression_dataset_path: Optional[str] = None,
) -> Dict[str, Any]:
    run_row = _start_learning_run(twin_id=twin_id, tenant_id=tenant_id, created_by=created_by)
    run_id = run_row.get("id") if run_row else None

    try:
        events = _fetch_unprocessed_events(twin_id=twin_id, limit=max(1, int(event_limit)))
        judge_rows = _fetch_recent_judge_results(twin_id=twin_id, limit=max(1, int(judge_limit)))
        modules = _fetch_modules(twin_id=twin_id)

        global_signal, intent_signal, module_signal, processed_ids = _aggregate_signals(
            events=events,
            judge_rows=judge_rows,
        )

        update_summary = _update_modules_with_signals(
            modules=modules,
            global_signal=global_signal,
            intent_signal=intent_signal,
            module_signal=module_signal,
            max_confidence_delta=max_confidence_delta,
            activation_threshold=activation_threshold,
            archive_threshold=archive_threshold,
            run_id=run_id,
        )

        processed_count = _mark_events_processed(processed_ids)

        if run_regression_gate:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            default_out = (
                Path(__file__).resolve().parents[2]
                / "docs"
                / "ai"
                / "improvements"
                / "proof_outputs"
                / f"phase7_feedback_learning_gate_{timestamp}.json"
            )
            gate_summary = run_persona_regression(
                dataset_path=regression_dataset_path,
                output_path=str(default_out),
            )
        else:
            gate_summary = {"skipped": True, "gate": {"passed": True}}

        gate_passed = bool((gate_summary.get("gate") or {}).get("passed", False))
        publish_candidate_version = None
        publish_decision = "held"
        published_row = None

        if auto_publish and gate_passed:
            publish_candidate_version = _latest_draft_spec_version(twin_id)
            if publish_candidate_version:
                published_row = publish_persona_spec(
                    twin_id=twin_id,
                    version=publish_candidate_version,
                )
                publish_decision = "published" if published_row else "held"
            else:
                publish_decision = "no_candidate"

        summary = {
            "status": "completed",
            "run_id": run_id,
            "twin_id": twin_id,
            "events_scanned": len(events),
            "events_processed": processed_count,
            "judge_rows_scanned": len(judge_rows),
            "min_events": min_events,
            "enough_events": len(events) >= min_events,
            "signals": {
                "global_signal": round(global_signal, 6),
                "intent_signal": {k: round(v, 6) for k, v in intent_signal.items()},
                "module_signal_count": len(module_signal),
            },
            "modules_updated": update_summary["modules_updated"],
            "avg_confidence_delta": update_summary["avg_confidence_delta"],
            "module_updates": update_summary["updates"][:50],
            "gate_summary": gate_summary,
            "publish_candidate_version": publish_candidate_version,
            "publish_decision": publish_decision,
            "published_spec": published_row,
        }

        if run_id:
            _finalize_learning_run(
                run_id=run_id,
                payload={
                    "status": "completed",
                    "events_scanned": len(events),
                    "modules_updated": update_summary["modules_updated"],
                    "avg_confidence_delta": update_summary["avg_confidence_delta"],
                    "publish_candidate_version": publish_candidate_version,
                    "publish_decision": publish_decision,
                    "gate_summary": gate_summary,
                    "summary": summary,
                },
            )
        return summary
    except Exception as e:
        error_summary = {
            "status": "failed",
            "run_id": run_id,
            "twin_id": twin_id,
            "error": str(e),
        }
        if run_id:
            _finalize_learning_run(
                run_id=run_id,
                payload={
                    "status": "failed",
                    "summary": error_summary,
                    "gate_summary": {"gate": {"passed": False}, "error": str(e)},
                    "publish_decision": "held",
                },
            )
        return error_summary
