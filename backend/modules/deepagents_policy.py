from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_UUID_PATTERN = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\b",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_ISO_DATETIME_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z\b")
_URL_PATTERN = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)

_EMAIL_ACTION_PATTERN = re.compile(r"\b(send|draft|write|compose)\b.*\b(email|mail)\b", re.IGNORECASE)
_SCHEDULE_ACTION_PATTERN = re.compile(
    r"\b(schedule|book|arrange|set up|create)\b.*\b(calendar|meeting|appointment|event)\b",
    re.IGNORECASE,
)
_WEBHOOK_ACTION_PATTERN = re.compile(r"\b(run|execute|trigger)\b.*\b(webhook|workflow|automation)\b", re.IGNORECASE)
_TASK_ACTION_PATTERN = re.compile(r"\b(create|add|open)\b.*\b(task|todo|to-?do)\b", re.IGNORECASE)
_NOTIFY_ACTION_PATTERN = re.compile(r"\b(notify|alert|inform|escalate)\b", re.IGNORECASE)

_SUBJECT_PATTERN = re.compile(
    r"\bsubject\s*[:=\-]\s*(.+?)(?:\s+\bbody\s*[:=\-]|\s*$)",
    re.IGNORECASE,
)
_BODY_PATTERN = re.compile(r"\bbody\s*[:=\-]\s*(.+)$", re.IGNORECASE)
_TITLE_PATTERN = re.compile(r"\b(?:title|about|for)\s*[:=\-]?\s*(.+?)(?:\s+\b(?:at|on)\b|\s*$)", re.IGNORECASE)
_METHOD_PATTERN = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b", re.IGNORECASE)
_DURATION_PATTERN = re.compile(
    r"\b(\d{1,3})\s*(minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)
_MESSAGE_PATTERN = re.compile(r"\b(?:notify|alert|inform|escalate)\b\s*(?:me|owner)?\s*(?:that)?\s*(.+)$", re.IGNORECASE)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip())


def _extract_action_id(query: str) -> Optional[str]:
    match = _UUID_PATTERN.search(query or "")
    if match:
        return match.group(1)
    return None


def _extract_email_inputs(query: str) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    addresses = [m.group(0) for m in _EMAIL_PATTERN.finditer(query or "")]
    if addresses:
        inputs["to"] = addresses[0]

    subject = _SUBJECT_PATTERN.search(query or "")
    if subject:
        raw_subject = re.sub(r"\s+", " ", subject.group(1)).strip()
        if raw_subject:
            inputs["subject"] = raw_subject

    body = _BODY_PATTERN.search(query or "")
    if body:
        raw_body = re.sub(r"\s+", " ", body.group(1)).strip()
        if raw_body:
            inputs["body"] = raw_body

    return inputs


def _extract_schedule_inputs(query: str) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}

    title = _TITLE_PATTERN.search(query or "")
    if title:
        raw_title = re.sub(r"\s+", " ", title.group(1)).strip().strip(".")
        if raw_title:
            inputs["title"] = raw_title

    start = _ISO_DATETIME_PATTERN.search(query or "")
    if start:
        inputs["start_time"] = start.group(0)

    duration = _DURATION_PATTERN.search(query or "")
    if duration:
        value = int(duration.group(1))
        unit = duration.group(2).lower()
        if unit.startswith("hour") or unit.startswith("hr"):
            value *= 60
        inputs["duration_minutes"] = value

    attendees = [m.group(0) for m in _EMAIL_PATTERN.finditer(query or "")]
    if attendees:
        inputs["attendees"] = attendees

    return inputs


def _extract_webhook_inputs(query: str) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    url = _URL_PATTERN.search(query or "")
    if url:
        inputs["url"] = url.group(0)
    method = _METHOD_PATTERN.search(query or "")
    if method:
        inputs["method"] = method.group(1).upper()
    return inputs


def _extract_notify_inputs(query: str) -> Dict[str, Any]:
    message = _MESSAGE_PATTERN.search(query or "")
    if message:
        parsed = re.sub(r"\s+", " ", message.group(1)).strip().strip(".")
        if parsed:
            return {"message": parsed}
    normalized = _normalize_query(query)
    return {"message": normalized[:500]} if normalized else {}


def _detect_action_type(query: str) -> Optional[str]:
    if _EMAIL_ACTION_PATTERN.search(query):
        return "draft_email"
    if _SCHEDULE_ACTION_PATTERN.search(query):
        return "draft_calendar_event"
    if _WEBHOOK_ACTION_PATTERN.search(query):
        return "webhook"
    if _TASK_ACTION_PATTERN.search(query):
        return "notify_owner"
    if _NOTIFY_ACTION_PATTERN.search(query):
        return "notify_owner"
    return None


def _required_params_for_action(action_type: str) -> List[str]:
    if action_type == "draft_email":
        return ["to", "subject", "body"]
    if action_type == "draft_calendar_event":
        return ["title", "start_time"]
    if action_type == "webhook":
        return ["url"]
    return []


def _tools_for_action(action_type: str) -> List[str]:
    if action_type == "draft_email":
        return ["gmail_draft"]
    if action_type == "draft_calendar_event":
        return ["google_calendar"]
    if action_type == "webhook":
        return ["http_webhook"]
    if action_type == "notify_owner":
        return ["owner_notification"]
    return []


def _steps_for_action(action_type: str, missing_params: List[str]) -> List[str]:
    if action_type == "draft_email":
        return [
            "Validate recipient, subject, and message body.",
            "Create a draft email payload with the provided details.",
            "Submit the draft for approval or execution.",
        ]
    if action_type == "draft_calendar_event":
        return [
            "Validate event title and start time.",
            "Prepare calendar event payload and optional attendees.",
            "Create event draft for approval or execute when allowed.",
        ]
    if action_type == "webhook":
        return [
            "Validate webhook URL and optional HTTP method.",
            "Prepare request payload.",
            "Execute webhook call when approved.",
        ]
    if action_type == "notify_owner":
        return [
            "Capture requested action summary.",
            "Prepare owner notification payload.",
            "Queue notification for approval or execution.",
        ]
    fallback = ["Analyze requested tool action.", "Collect required parameters.", "Execute with audit logging."]
    if missing_params:
        fallback.insert(1, f"Request missing parameters: {', '.join(missing_params)}.")
    return fallback


def _summary_for_action(action_type: str, missing_params: List[str]) -> str:
    if action_type == "draft_email":
        base = "Draft an email using provided recipient, subject, and body."
    elif action_type == "draft_calendar_event":
        base = "Draft a calendar event using provided title and start time."
    elif action_type == "webhook":
        base = "Execute a workflow webhook request."
    elif action_type == "notify_owner":
        base = "Create a notification/task-style action for the owner."
    else:
        base = "Execute requested tool action."
    if missing_params:
        return f"{base} Missing: {', '.join(missing_params)}."
    return base


def classify_deepagents_intent(query: str) -> Dict[str, Any]:
    normalized = _normalize_query(query)
    lowered = normalized.lower()
    result: Dict[str, Any] = {
        "query": normalized,
        "is_action_or_control": False,
        "control_action": None,
        "target_action_id": None,
        "action_type": None,
        "inputs": {},
        "required_params": [],
        "missing_params": [],
        "tools": [],
        "steps": [],
        "summary": "",
        "reason": "",
    }
    if not lowered:
        return result

    target_action_id = _extract_action_id(normalized)
    if "approve" in lowered and target_action_id:
        result.update(
            {
                "is_action_or_control": True,
                "control_action": "approve",
                "target_action_id": target_action_id,
                "summary": f"Approve pending action {target_action_id}.",
                "reason": "explicit_approval_command",
                "steps": [
                    "Validate the referenced action ID.",
                    "Approve the action draft.",
                    "Execute the approved action and log outcome.",
                ],
            }
        )
        return result

    if any(k in lowered for k in ("cancel", "reject", "deny")) and target_action_id:
        result.update(
            {
                "is_action_or_control": True,
                "control_action": "cancel",
                "target_action_id": target_action_id,
                "summary": f"Cancel pending action {target_action_id}.",
                "reason": "explicit_cancel_command",
                "steps": [
                    "Validate the referenced action ID.",
                    "Reject/cancel the action draft.",
                    "Record cancellation in audit trail.",
                ],
            }
        )
        return result

    action_type = _detect_action_type(normalized)
    if not action_type:
        return result

    if action_type == "draft_email":
        inputs = _extract_email_inputs(normalized)
    elif action_type == "draft_calendar_event":
        inputs = _extract_schedule_inputs(normalized)
    elif action_type == "webhook":
        inputs = _extract_webhook_inputs(normalized)
    else:
        inputs = _extract_notify_inputs(normalized)

    required_params = _required_params_for_action(action_type)
    missing_params = [key for key in required_params if not inputs.get(key)]

    result.update(
        {
            "is_action_or_control": True,
            "control_action": None,
            "target_action_id": None,
            "action_type": action_type,
            "inputs": inputs,
            "required_params": required_params,
            "missing_params": missing_params,
            "tools": _tools_for_action(action_type),
            "steps": _steps_for_action(action_type, missing_params),
            "summary": _summary_for_action(action_type, missing_params),
            "reason": "tool_action_detected",
        }
    )
    return result
