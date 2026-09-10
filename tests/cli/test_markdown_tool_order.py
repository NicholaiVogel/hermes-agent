"""Codex tool events are display boundaries even without a stream None sentinel."""
from types import SimpleNamespace

import pytest

from agent.codex_runtime import make_codex_app_server_event_bridge
from cli import HermesCLI


@pytest.mark.parametrize('mode', ['render', 'raw', 'strip'])
@pytest.mark.parametrize('completed_only', [False, True])
def test_codex_tools_keep_assistant_messages_in_event_order(monkeypatch, completed_only, mode):
    import cli as facade
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = mode
    cli.show_timestamps = False
    cli.tool_progress_mode = 'all'
    cli._pending_tool_info = {}
    cli._last_scrollback_tool = None
    cli._turn_summary_record = lambda *args: None
    cli._invalidate = lambda *args, **kwargs: None
    cli._reset_stream_state()
    bridge = make_codex_app_server_event_bridge(SimpleNamespace(
        _fire_stream_delta=cli._stream_delta, tool_progress_callback=cli._on_tool_progress))
    emitted.append('USER: Read my note')
    bridge({'method': 'item/agentMessage/delta', 'params': {'delta': "I'll find your note."}})
    item = {'id': 'tool-one', 'type': 'commandExecution', 'command': 'cat note.md',
            'aggregatedOutput': 'Today I wrote a regression test.', 'exitCode': 0, 'durationMs': 10}
    if not completed_only:
        bridge({'method': 'item/started', 'params': {'item': item}})
        assert "I'll find your note." in '\n'.join(emitted)
        assert cli._markdown_stream is None
    bridge({'method': 'item/completed', 'params': {'item': item}})
    bridge({'method': 'item/agentMessage/delta', 'params': {'delta': 'Here is your note.'}})
    cli._flush_stream()
    output = '\n'.join(emitted)
    assert output.index('USER:') < output.index("I'll find") < output.index('exec_comm') < output.index('Here is')
    assert output.count("I'll find your note.") == output.count('Here is your note.') == 1
    assert not any("I'll find" in entry and 'Here is' in entry for entry in emitted)
