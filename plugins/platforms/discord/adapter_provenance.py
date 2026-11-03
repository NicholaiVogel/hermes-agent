"""Discord reply provenance extracted only from resolved native message references."""

from typing import Any


def reply_metadata(reference: Any, bot_user: Any) -> dict[str, Any]:
    if reference is None or getattr(reference, "message_id", None) is None:
        return {}
    fields: dict[str, Any] = {"reply_to_message_id": str(reference.message_id)}
    resolved = getattr(reference, "resolved", None)
    if resolved is None:
        return fields
    fields["reply_to_text"] = getattr(resolved, "content", None) or None
    author = getattr(resolved, "author", None)
    author_id = getattr(author, "id", None)
    if author_id is None:
        return fields
    bot_id = getattr(bot_user, "id", None)
    fields.update(
        reply_to_author_id=str(author_id),
        reply_to_author_name=getattr(author, "display_name", None) or None,
        reply_to_author_username=getattr(author, "name", None) or None,
        reply_to_is_own_message=bot_id is not None and author_id == bot_id,
    )
    return fields
