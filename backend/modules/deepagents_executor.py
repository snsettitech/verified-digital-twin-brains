from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, Optional

from modules.actions_engine import ActionDraftManager, ActionExecutor
from modules.governance import AuditLogger


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 100) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    values = []
    for item in raw.split(","):
        parsed = item.strip()
        if parsed:
            values.append(parsed)
    return values


def deepagents_config() -> Dict[str, Any]:
    return {
        "enabled": _env_bool("DEEPAGENTS_ENABLED", False),
        "require_approval": _env_bool("DEEPAGENTS_REQUIRE_APPROVAL", True),
        "max_steps": _env_int("DEEPAGENTS_MAX_STEPS", 6, minimum=1, maximum=25),
        "timeout_seconds": _env_int("DEEPAGENTS_TIMEOUT_SECONDS", 20, minimum=1, maximum=180),
        "allowlist_twin_ids": _env_csv("DEEPAGENTS_ALLOWLIST_TWIN_IDS"),
        "allowlist_tenant_ids": _env_csv("DEEPAGENTS_ALLOWLIST_TENANT_IDS"),
    }


def _is_allowlisted(config: Dict[str, Any], *, twin_id: str, tenant_id: Optional[str]) -> bool:
    allowed_twins = {str(v).strip() for v in (config.get("allowlist_twin_ids") or []) if str(v).strip()}
    allowed_tenants = {str(v).strip() for v in (config.get("allowlist_tenant_ids") or []) if str(v).strip()}
    if not allowed_twins and not allowed_tenants:
        return True
    if twin_id and twin_id in allowed_twins:
        return True
    if tenant_id and tenant_id in allowed_tenants:
        return True
    return False


def _clean_preview(value: Any, *, max_len: int = 300) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    return cleaned[:max_len]


def _audit(
    *,
    tenant_id: Optional[str],
    twin_id: str,
    actor_id: Optional[str],
    action: str,
    metadata: Dict[str, Any],
) -> None:
    if not tenant_id:
        return
    try:
        AuditLogger.log(
            tenant_id=tenant_id,
            event_type="ACTION_AUTOMATION",
            action=action,
            twin_id=twin_id,
            actor_id=actor_id,
            metadata=metadata,
        )
    except Exception:
        pass


def _disabled_result(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "http_status": 501,
        "error": {
            "code": "DEEPAGENTS_DISABLED",
            "message": "DEEPAGENTS_ENABLED is disabled for this deployment.",
        },
        "config": config,
    }


async def execute_deepagents_plan(
    *,
    twin_id: str,
    plan: Dict[str, Any],
    actor_user_id: Optional[str],
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    interaction_context: Optional[str] = None,
) -> Dict[str, Any]:
    config = deepagents_config()
    if not config["enabled"]:
        return _disabled_result(config)

    normalized_context = str(interaction_context or "").strip().lower()
    if not actor_user_id or normalized_context in {"public_share", "public_widget"}:
        return {
            "status": "forbidden",
            "http_status": 403,
            "error": {
                "code": "DEEPAGENTS_FORBIDDEN_CONTEXT",
                "message": "Action execution is unavailable in public or anonymous contexts.",
            },
            "config": config,
        }

    if not _is_allowlisted(config, twin_id=twin_id, tenant_id=tenant_id):
        _audit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            actor_id=actor_user_id,
            action="DEEPAGENTS_FORBIDDEN_ALLOWLIST",
            metadata={
                "conversation_id": conversation_id,
                "interaction_context": normalized_context or "owner_chat",
            },
        )
        return {
            "status": "forbidden",
            "http_status": 403,
            "error": {
                "code": "DEEPAGENTS_NOT_ALLOWLISTED",
                "message": "Action execution is not enabled for this twin or tenant.",
            },
            "config": config,
        }

    control_action = str(plan.get("control_action") or "").strip().lower()
    target_action_id = str(plan.get("target_action_id") or "").strip() or None

    if control_action in {"approve", "cancel"}:
        if not target_action_id:
            return {
                "status": "missing_params",
                "missing_params": ["target_action_id"],
                "clarification_question": "Please share the action ID you want to approve or cancel.",
                "config": config,
            }
        if control_action == "approve":
            ok = await asyncio.wait_for(
                asyncio.to_thread(
                    ActionDraftManager.approve_draft,
                    target_action_id,
                    actor_user_id or "system",
                    "Approved via deepagents execution lane",
                ),
                timeout=config["timeout_seconds"],
            )
            _audit(
                tenant_id=tenant_id,
                twin_id=twin_id,
                actor_id=actor_user_id,
                action="DEEPAGENTS_APPROVED",
                metadata={
                    "action_id": target_action_id,
                    "conversation_id": conversation_id,
                },
            )
            return {
                "status": "approved" if ok else "failed",
                "action_id": target_action_id,
                "message": "Action approved and executed." if ok else "Failed to approve action.",
                "config": config,
            }

        ok = await asyncio.wait_for(
            asyncio.to_thread(
                ActionDraftManager.reject_draft,
                target_action_id,
                actor_user_id or "system",
                "Canceled via deepagents execution lane",
            ),
            timeout=config["timeout_seconds"],
        )
        _audit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            actor_id=actor_user_id,
            action="DEEPAGENTS_CANCELED",
            metadata={
                "action_id": target_action_id,
                "conversation_id": conversation_id,
            },
        )
        return {
            "status": "canceled" if ok else "failed",
            "action_id": target_action_id,
            "message": "Action canceled." if ok else "Failed to cancel action.",
            "config": config,
        }

    action_type = str(plan.get("action_type") or "").strip().lower()
    if not action_type:
        return {
            "status": "unsupported",
            "message": "No supported action type detected.",
            "config": config,
        }

    missing_params = [str(v) for v in (plan.get("missing_params") or []) if str(v).strip()]
    if missing_params:
        return {
            "status": "missing_params",
            "missing_params": missing_params,
            "config": config,
        }

    steps = [str(step).strip() for step in (plan.get("steps") or []) if str(step).strip()]
    max_steps = int(config["max_steps"])
    step_limited = steps[:max_steps]
    step_truncated = len(steps) > len(step_limited)

    inputs = dict(plan.get("inputs") or {})
    inputs["_deepagents_steps"] = step_limited
    inputs["_deepagents_step_truncated"] = step_truncated
    inputs["_deepagents_summary"] = _clean_preview(plan.get("summary") or "")
    inputs["_deepagents_tools"] = list(plan.get("tools") or [])
    inputs["_deepagents_required_params"] = list(plan.get("required_params") or [])

    proposed_action = {
        "action_type": action_type,
        "connector_id": inputs.get("connector_id"),
        "config": inputs,
    }
    context = {
        "trigger_name": "deepagents_chat",
        "event_type": "chat_action_request",
        "user_message": _clean_preview(plan.get("query"), max_len=500),
        "match_conditions": {"lane": "deepagents"},
        "deepagents_plan": {
            "tools": list(plan.get("tools") or []),
            "required_params": list(plan.get("required_params") or []),
            "steps": step_limited,
            "step_truncated": step_truncated,
        },
    }

    if config["require_approval"]:
        action_id = await asyncio.wait_for(
            asyncio.to_thread(
                ActionDraftManager.create_draft,
                twin_id,
                None,
                None,
                proposed_action,
                context,
            ),
            timeout=config["timeout_seconds"],
        )
        if not action_id:
            return {
                "status": "failed",
                "message": "Failed to create pending action draft.",
                "config": config,
            }
        _audit(
            tenant_id=tenant_id,
            twin_id=twin_id,
            actor_id=actor_user_id,
            action="DEEPAGENTS_PLAN_CREATED",
            metadata={
                "action_id": action_id,
                "action_type": action_type,
                "conversation_id": conversation_id,
                "require_approval": True,
                "step_count": len(step_limited),
            },
        )
        return {
            "status": "needs_approval",
            "action_id": action_id,
            "action_type": action_type,
            "step_count": len(step_limited),
            "config": config,
        }

    execution_id = await asyncio.wait_for(
        asyncio.to_thread(
            ActionExecutor.execute_action,
            twin_id=twin_id,
            action_type=action_type,
            inputs=inputs,
            trigger_id=None,
            draft_id=None,
            connector_id=inputs.get("connector_id"),
            executed_by=actor_user_id,
        ),
        timeout=config["timeout_seconds"],
    )
    if not execution_id:
        return {
            "status": "failed",
            "message": "Action execution failed.",
            "action_type": action_type,
            "config": config,
        }
    execution = await asyncio.to_thread(ActionExecutor.get_execution_details, execution_id)
    _audit(
        tenant_id=tenant_id,
        twin_id=twin_id,
        actor_id=actor_user_id,
        action="DEEPAGENTS_EXECUTED",
        metadata={
            "execution_id": execution_id,
            "action_type": action_type,
            "conversation_id": conversation_id,
            "step_count": len(step_limited),
            "require_approval": False,
        },
    )
    return {
        "status": "executed",
        "execution_id": execution_id,
        "action_type": action_type,
        "step_count": len(step_limited),
        "execution": execution or {},
        "config": config,
    }
