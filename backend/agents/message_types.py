"""
Plain-dict message abstraction replacing LangChain's HumanMessage/AIMessage/BaseMessage.

All agent code uses these lightweight factories instead of langchain_core.messages.
The dict format matches what inference_router.py already expects:
  {"role": "user"|"assistant"|"system", "content": "..."}
"""

from typing import Any, Dict, List, Optional


# ---------- constructors ----------

def human_message(content: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a user message dict (replaces HumanMessage)."""
    return {"role": "user", "content": content, "type": "human", **kwargs}


def ai_message(content: str, **kwargs: Any) -> Dict[str, Any]:
    """Create an assistant message dict (replaces AIMessage)."""
    msg: Dict[str, Any] = {
        "role": "assistant",
        "content": content,
        "type": "ai",
        "additional_kwargs": {},
    }
    msg.update(kwargs)
    return msg


def system_message(content: str) -> Dict[str, Any]:
    """Create a system message dict."""
    return {"role": "system", "content": content, "type": "system"}


# ---------- accessors ----------

def get_content(msg: Dict[str, Any]) -> str:
    """Extract content from a message dict."""
    return str(msg.get("content") or "")


def get_role(msg: Dict[str, Any]) -> str:
    """Extract role from a message dict."""
    return str(msg.get("role") or "user")


def is_human(msg: Dict[str, Any]) -> bool:
    """Check if message is from a human/user."""
    return msg.get("type") == "human" or msg.get("role") == "user"


def is_ai(msg: Dict[str, Any]) -> bool:
    """Check if message is from the assistant."""
    return msg.get("type") == "ai" or msg.get("role") == "assistant"


def get_last_human_content(messages: List[Dict[str, Any]]) -> str:
    """Get content of the last human message in a list."""
    for msg in reversed(messages):
        if is_human(msg):
            return get_content(msg)
    return ""


def get_additional_kwargs(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Get additional_kwargs from a message dict (replaces msg.additional_kwargs)."""
    return msg.get("additional_kwargs", {})


def set_additional_kwarg(msg: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    """Set a key in additional_kwargs, returning a new message (immutable)."""
    new_msg = {**msg}
    new_msg["additional_kwargs"] = {**new_msg.get("additional_kwargs", {}), key: value}
    return new_msg


# ---------- conversion helpers ----------

def from_langchain(lc_msg) -> Dict[str, Any]:
    """Convert a LangChain BaseMessage to our plain dict format.
    Useful during migration to handle mixed message types.
    """
    content = getattr(lc_msg, "content", "")
    msg_type = getattr(lc_msg, "type", "human")
    role = "user" if msg_type == "human" else "assistant" if msg_type == "ai" else "system"
    additional = dict(getattr(lc_msg, "additional_kwargs", {}))
    return {
        "role": role,
        "content": content,
        "type": msg_type,
        "additional_kwargs": additional,
    }


def to_inference_format(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert to the format inference_router.invoke_text() expects:
    [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    return [{"role": get_role(m), "content": get_content(m)} for m in messages]


def from_db_history(raw_history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Convert database conversation history rows to our message format.
    Input: [{"role": "user"|"assistant", "content": "..."}]
    """
    result = []
    for msg in raw_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            result.append(human_message(content))
        elif role == "assistant":
            result.append(ai_message(content))
    return result
