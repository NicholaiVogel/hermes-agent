"""gateway_message_context: real hook dispatch through shared prepare + busy steer paths."""

import asyncio
import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.event import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli.plugins import get_plugin_manager


@pytest.fixture
def hook():
    manager = get_plugin_manager()
    manager._discovered = True
    calls, registered = [], []

    def register(cb):
        manager._hooks.setdefault("gateway_message_context", []).append(cb)
        registered.append(cb)

    yield calls, register
    for cb in registered:
        manager._hooks["gateway_message_context"].remove(cb)


def _runner():
    return GatewayRunner(config=GatewayConfig())


def _event(user, text="hello", **kw):
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="c", chat_type="group",
                           user_id=user, message_id="m-" + user)
    return MessageEvent(text=text, source=source, message_id="msg-" + user, **kw), source


def _recorder(calls):
    def cb(**kw):
        calls.append(kw)
        return {"context": f"<who {kw['source']['user_id']} {kw['delivery_path']}>"}
    return cb


@pytest.mark.asyncio
@pytest.mark.parametrize("persist", [True, False, "true"])
async def test_only_explicit_durable_context_is_retained_in_transcript(hook, persist):
    _, register = hook
    register(lambda **kw: {"context": "stable audit attachment", "persist": persist})
    register(lambda **kw: {"context": "ephemeral API context"})
    event, source = _event("alice", "user words")
    runner = _runner()
    wire = await runner._prepare_profile_scoped_inbound_message_text(
        event=event, source=source, history=[], session_key="k")
    _, transcript, _ = runner._hmwa_apply_message_timestamp(event, wire)
    assert isinstance(wire, str) and isinstance(transcript, str)
    assert "stable audit attachment" in wire and "ephemeral API context" in wire
    assert ("stable audit attachment" in transcript) is (persist is True)
    assert "ephemeral API context" not in transcript
    assert "user words" in transcript and event.text == "user words"


@pytest.mark.asyncio
async def test_prepare_injects_per_speaker_context_and_body_free_payload(hook):
    calls, register = hook
    register(_recorder(calls))
    runner = _runner()
    out = []
    for user in ("alice", "bob"):
        event, source = _event(user, "secret body")
        out.append(await runner._prepare_profile_scoped_inbound_message_text(
            event=event, source=source, history=[], session_key="k"))
    assert "<who alice turn>" in out[0] and "<who bob turn>" in out[1]
    assert out[0].count("secret body") == 1
    for call in calls:
        assert "text" not in call and "secret body" not in repr(call)
        assert call["internal"] is False and call["delivery_path"] == "turn"
        assert call["source"]["user_id"] in ("alice", "bob")


@pytest.mark.asyncio
async def test_async_context_hook_does_not_block_gateway_loop(hook, monkeypatch):
    _, register = hook
    entered, release = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr("hermes_cli.plugins._resolve_hook_callback_timeout", lambda: 2.0)

    async def callback(**kwargs):
        entered.set()
        await release.wait()
        return {"context": "loop remained responsive"}

    register(callback)
    event, source = _event("alice", "body")
    task = asyncio.create_task(_runner()._prepare_profile_scoped_inbound_message_text(
        event=event, source=source, history=[], session_key="k"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=4)
        release.set()
        result = await asyncio.wait_for(task, timeout=4)
        assert "loop remained responsive" in result
    finally:
        release.set()
        if not task.done():
            task.cancel()


@pytest.mark.asyncio
async def test_concurrent_messages_with_same_local_id_in_different_chats_both_get_context(hook):
    _, register = hook
    entered, release = asyncio.Queue(), asyncio.Event()

    async def callback(**kwargs):
        entered.put_nowait(kwargs["source"]["user_id"])
        await release.wait()
        return {"context": f"speaker:{kwargs['source']['user_id']}"}

    register(callback)
    runner = _runner()
    events = [_event(name, "body") for name in ("alice", "bob")]
    tasks = []
    for event, source in events:
        source.chat_id = source.user_id
        event.message_id = "same-local-message-id"
        tasks.append(asyncio.create_task(runner._prepare_profile_scoped_inbound_message_text(
            event=event, source=source, history=[], session_key=source.chat_id)))
    try:
        names = {await asyncio.wait_for(entered.get(), timeout=4),
                 await asyncio.wait_for(entered.get(), timeout=4)}
        assert names == {"alice", "bob"}
    finally:
        release.set()
        results = await asyncio.gather(*tasks)
    assert "speaker:alice" in results[0] and "speaker:bob" in results[1]


@pytest.mark.asyncio
async def test_reply_snapshot_and_internal_flag(hook):
    calls, register = hook
    register(_recorder(calls))
    event, source = _event("alice", internal=True, reply_to_message_id="r1")
    event.reply_to_text = "quoted"
    await _runner()._prepare_profile_scoped_inbound_message_text(
        event=event, source=source, history=[], session_key="k")
    assert calls[0]["internal"] is True
    assert calls[0]["reply_to"] == {"message_id": "r1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["raise", "none", "empty"])
async def test_hook_failure_preserves_normal_text(hook, bad):
    _, register = hook

    def cb(**kw):
        if bad == "raise":
            raise RuntimeError("boom")
        return None if bad == "none" else {"context": "  "}

    register(cb)
    event, source = _event("alice", "plain")
    out = await _runner()._prepare_profile_scoped_inbound_message_text(
        event=event, source=source, history=[], session_key="k")
    assert out.endswith("plain") and "boom" not in out


@pytest.mark.asyncio
async def test_busy_steer_gets_context_and_keeps_origin(hook):
    from types import SimpleNamespace
    calls, register = hook
    register(_recorder(calls))
    event, source = _event("bob", "/steer steer me")
    runner, injected = _runner(), []
    runner._session_state("k").turn.agent = SimpleNamespace(steer=lambda text: injected.append(text) or True)
    await runner._busy_steer_command(event, "k", source)
    assert len(injected) == 1
    assert "<who bob steer>" in injected[0]
    assert "Gateway message origin" in injected[0] and injected[0].endswith("steer me")
    assert calls[0]["delivery_path"] == "steer"


@pytest.mark.asyncio
async def test_busy_steer_hook_failure_is_open(hook):
    from types import SimpleNamespace
    _, register = hook
    register(lambda **kw: (_ for _ in ()).throw(RuntimeError("x")))
    event, source = _event("bob", "/steer steer me")
    runner, injected = _runner(), []
    runner._session_state("k").turn.agent = SimpleNamespace(steer=lambda text: injected.append(text) or True)
    await runner._busy_steer_command(event, "k", source)
    assert len(injected) == 1
    assert "Gateway message origin" in injected[0] and injected[0].endswith("steer me")


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["priority_steer", "priority_redirect"])
async def test_priority_busy_paths_get_context(hook, route):
    calls, register = hook
    register(_recorder(calls))
    event, source = _event("bob", "follow up")
    runner = _runner()

    class Receiver:
        _supports_active_turn_redirect = True
        payload = None

        def steer(self, text):
            self.payload = text
            return True

        redirect = steer

    receiver = Receiver()
    runner._session_state("k").turn.agent = receiver
    if route == "priority_steer":
        await runner._hm_busy_steer(event, receiver, "k")
    else:
        await runner._hm_busy_interrupt(event, source, receiver, "k")
    assert "<who bob steer>" in receiver.payload and receiver.payload.endswith("follow up")
    assert calls[0]["delivery_path"] == "steer"
