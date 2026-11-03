"""Per-message plugin context for gateway turns (``gateway_message_context`` hook)."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

HOOK_NAME = "gateway_message_context"


def discord_triggering_note(message_id: Any) -> str:
    """Model-facing routing note for a Discord turn (rides the API-bound user message only)."""
    return (
        f"[Triggering message id: `{message_id}` — use as `message_id` for reply/react/pin "
        f"via the discord tools.]"
    )


def strip_discord_triggering_note(event: Any, message_text: Any) -> Any:
    """Peel off only this event's generated routing note from authored transcript content."""
    message_id = getattr(event, "message_id", None)
    if not message_id or not isinstance(message_text, str):
        return message_text
    return message_text.removeprefix(f"{discord_triggering_note(message_id)}\n\n")


def _reply_snapshot(event: Any) -> Optional[dict[str, Any]]:
    fields = {
        "message_id": getattr(event, "reply_to_message_id", None),
        "user_id": getattr(event, "reply_to_author_id", None),
        "display_name": getattr(event, "reply_to_author_name", None),
        "username": getattr(event, "reply_to_author_username", None),
    }
    fields = {k: str(v) for k, v in fields.items() if v not in (None, "")}
    return fields or None


def build_message_context_payload(
    event: Any, source: Any, delivery_path: str, session_key: Optional[str] = None,
) -> dict[str, Any]:
    """Plain, body-free snapshot: no message text, SDK objects or host handles."""
    platform = getattr(source, "platform", None)
    payload: dict[str, Any] = {
        "platform": str(getattr(platform, "value", platform) or ""),
        "source": source.to_dict(),
        "message_id": getattr(event, "message_id", None) or getattr(source, "message_id", None),
        "internal": bool(getattr(event, "internal", False)),
        "delivery_path": delivery_path,
    }
    if session_key:
        payload["session_key"] = session_key
    reply = _reply_snapshot(event)
    if reply:
        payload["reply_to"] = reply
    return payload


def message_context_for_transcript(event: Any, text: Any) -> Any:
    """Retain opted-in context verbatim; remove only the exact model-only receipt."""
    suffix = getattr(event, "_gateway_message_context_suffix", None)
    if not isinstance(text, str) or not suffix or not text.endswith(suffix):
        return text
    durable = getattr(event, "_gateway_message_context_persisted_suffix", None) or ""
    return text.removesuffix(suffix) + durable


async def collect_message_context(
    event: Any, source: Any, delivery_path: str, session_key: Optional[str] = None,
) -> str:
    """Await the fail-open hook without blocking the gateway loop; join non-empty context."""
    event._gateway_message_context_persisted_suffix = None
    try:
        from hermes_cli.lifecycle import ainvoke_hook

        results = await ainvoke_hook(HOOK_NAME, **build_message_context_payload(
            event, source, delivery_path, session_key))
        parts, durable_parts = [], []
        for result in results or []:
            value = result.get("context") if isinstance(result, dict) else result
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                if isinstance(result, dict) and result.get("persist") is True:
                    durable_parts.append(value.strip())
        if durable_parts:
            event._gateway_message_context_persisted_suffix = "\n\n" + "\n\n".join(durable_parts)
        return "\n\n".join(parts)
    except Exception:
        logger.warning("%s hook failed", HOOK_NAME, exc_info=True)
        return ""
