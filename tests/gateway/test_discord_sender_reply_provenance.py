"""Discord sender @username and quoted reply-author metadata are captured from the SDK objects only."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.event import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from plugins.platforms.discord.adapter import DiscordAdapter

_BOT = SimpleNamespace(id=999, name="hermesbot", display_name="Hermes")


class _DM:
    id = 55
    name = "dm"


def _adapter() -> DiscordAdapter:
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="fake"))
    adapter._client = SimpleNamespace(user=_BOT)
    adapter._text_batch_delay_seconds = 0
    adapter._discord_history_backfill = lambda: False
    adapter.handle_message = AsyncMock()
    return adapter


def _dm_message(reference=None, content="hello") -> SimpleNamespace:
    chan = _DM()
    return SimpleNamespace(
        id=1, content=content, mentions=[], attachments=[], reference=reference,
        created_at=datetime.now(UTC), channel=chan,
        author=SimpleNamespace(id=42, display_name="Alice Display", name="alice_acct", bot=False),
    )


async def _event(adapter: DiscordAdapter, message) -> MessageEvent:
    adapter._is_allowed_user = lambda *a, **k: True
    assert await adapter._handle_message(message)
    return adapter.handle_message.await_args.args[0]


def _ref(resolved, message_id=7) -> SimpleNamespace:
    return SimpleNamespace(message_id=message_id, resolved=resolved)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_ALLOW_ALL_USERS", "true")
    import plugins.platforms.discord.adapter as mod
    monkeypatch.setattr(mod.discord, "DMChannel", _DM, raising=False)


@pytest.mark.asyncio
async def test_sender_username_differs_from_display_name():
    event = await _event(_adapter(), _dm_message())
    assert event.source.user_name == "Alice Display"
    assert event.source.user_username == "alice_acct"
    assert event.source.user_id == "42"


@pytest.mark.asyncio
async def test_quoted_author_comes_from_resolved_message_not_sender():
    quoted = SimpleNamespace(
        content="old text", author=SimpleNamespace(id=77, display_name="Bob Display", name="bob_acct"))
    event = await _event(_adapter(), _dm_message(_ref(quoted)))
    assert (event.reply_to_author_id, event.reply_to_author_name, event.reply_to_author_username) == (
        "77", "Bob Display", "bob_acct")
    assert event.reply_to_is_own_message is False
    assert event.reply_to_author_id != event.source.user_id


@pytest.mark.asyncio
async def test_quoting_the_bot_marks_own_message():
    quoted = SimpleNamespace(content="mine", author=SimpleNamespace(id=999, display_name="Hermes", name="hermesbot"))
    event = await _event(_adapter(), _dm_message(_ref(quoted)))
    assert event.reply_to_is_own_message is True
    assert event.reply_to_author_id == "999"


@pytest.mark.asyncio
@pytest.mark.parametrize("resolved", [None, SimpleNamespace(id=7, channel_id=55, guild_id=None)])  # 2nd: real DeletedReferencedMessage shape (ids only)
async def test_missing_or_deleted_reference_leaves_author_unknown(resolved):
    # Text that looks like an author line must never be parsed into identity.
    event = await _event(_adapter(), _dm_message(_ref(resolved), content="Bob (@bob_acct) said hi"))
    assert event.reply_to_message_id == "7"
    assert event.reply_to_author_id is None
    assert event.reply_to_author_name is None
    assert event.reply_to_author_username is None
    assert event.reply_to_is_own_message is False


def test_legacy_source_json_roundtrips_with_none_username():
    legacy = {"platform": "discord", "chat_id": "1", "chat_name": None, "chat_type": "dm",
              "user_id": "2", "user_name": "A", "thread_id": None, "chat_topic": None}
    src = SessionSource.from_dict(legacy)
    assert src.user_username is None
    assert "user_username" not in src.to_dict()


def test_username_roundtrips_and_positional_order_is_stable():
    src = SessionSource(platform=Platform.DISCORD, chat_id="1", user_id="2", user_name="Disp", user_username="acct")
    assert SessionSource.from_dict(src.to_dict()).user_username == "acct"
    assert SessionSource.from_dict(src.to_dict()).user_name == "Disp"
    positional = SessionSource(Platform.DISCORD, "1", "name", "dm", "2", "Disp")
    assert positional.user_username is None and positional.user_name == "Disp"


@pytest.mark.asyncio
async def test_queue_clone_and_steer_fallback_preserve_metadata():
    runner = GatewayRunner(config=GatewayConfig())
    source = SessionSource(platform=Platform.DISCORD, chat_id="1", user_id="2", user_name="Disp",
                           user_username="acct", chat_type="group")
    event = MessageEvent(
        text="/queue do it", source=source, message_id="m", reply_to_message_id="7", reply_to_text="old",
        reply_to_author_id="77", reply_to_author_name="Bob Display", reply_to_is_own_message=True,
        reply_to_author_username="bob_acct")
    queued: list[MessageEvent] = []
    runner._delivery_adapter_for = lambda s: object()
    runner._enqueue_fifo = lambda key, ev, adapter: queued.append(ev)
    await runner._busy_queue_command(event, "key", source)
    steer = MessageEvent(text="/steer go", source=source, message_id="m2", reply_to_message_id="7",
                         reply_to_text="old", reply_to_author_id="77", reply_to_author_name="Bob Display",
                         reply_to_author_username="bob_acct", reply_to_is_own_message=True)
    await runner._busy_steer_command(steer, "key", source)
    assert len(queued) == 2
    for ev in queued:
        assert ev.source.user_username == "acct"
        assert (ev.reply_to_message_id, ev.reply_to_author_id, ev.reply_to_author_name,
                ev.reply_to_author_username, ev.reply_to_is_own_message) == (
            "7", "77", "Bob Display", "bob_acct", True)
