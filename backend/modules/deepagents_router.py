from __future__ import annotations

import re
from typing import Any, Dict, List

from modules.deepagents_policy import classify_deepagents_intent


def build_deepagents_plan(query: str, *, interaction_context: str | None = None) -> Dict[str, Any]:
    plan = classify_deepagents_intent(query)
    plan["interaction_context"] = (interaction_context or "").strip().lower() if interaction_context else None
    return plan


def _humanize_params(params: List[str]) -> str:
    labels = {
        "to": "recipient email",
        "subject": "email subject",
        "body": "email body",
        "title": "event title",
        "start_time": "start time (ISO format, e.g. 2026-03-01T10:00:00Z)",
        "url": "webhook URL",
    }
    rendered = [labels.get(param, param.replace("_", " ")) for param in params]
    return ", ".join(rendered)


def build_single_missing_param_question(plan: Dict[str, Any]) -> str:
    missing = plan.get("missing_params") or []
    if not isinstance(missing, list):
        missing = []

    action_type = str(plan.get("action_type") or "").strip().lower()
    if action_type == "draft_email":
        if set(missing) == {"to", "subject", "body"}:
            return "Please provide recipient email, subject, and body so I can draft the email."
        if missing:
            return f"Please provide {_humanize_params(missing)} so I can draft the email."
    if action_type == "draft_calendar_event":
        return (
            f"Please provide {_humanize_params(missing)} so I can prepare the calendar event."
            if missing
            else "Please provide the event details so I can continue."
        )
    if action_type == "webhook":
        return (
            f"Please provide {_humanize_params(missing)} so I can execute the workflow."
            if missing
            else "Please provide the webhook details so I can continue."
        )

    if missing:
        return f"Please provide {_humanize_params(missing)} so I can execute this action."

    summary = re.sub(r"\s+", " ", str(plan.get("summary") or "").strip())
    if summary:
        return f"I can run this action. What exact parameters should I use for: {summary}"
    return "I can run this action. What exact parameters should I use?"


def summarize_deepagents_plan(plan: Dict[str, Any]) -> str:
    summary = re.sub(r"\s+", " ", str(plan.get("summary") or "").strip())
    if summary:
        return summary
    action_type = str(plan.get("action_type") or "").strip().lower()
    if action_type:
        return f"Execute action type `{action_type}`."
    control_action = str(plan.get("control_action") or "").strip().lower()
    action_id = str(plan.get("target_action_id") or "").strip()
    if control_action and action_id:
        return f"{control_action.title()} pending action `{action_id}`."
    return "Execute requested action."
