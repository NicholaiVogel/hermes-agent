"""Notification styling must not change busy-input or slash-command routing."""
from queue import Queue
from types import SimpleNamespace

import pytest
from rich.text import Text

from cli import HermesCLI


@pytest.mark.parametrize('mode,label', [('queue', 'Queued for next turn'),
                                        ('steer', 'Steered'),
                                        ('interrupt', 'Redirected current turn')])
def test_busy_acknowledgments_share_quiet_layout_and_preserve_payload(monkeypatch, mode, label):
    import cli as facade
    emitted, accepted = [], []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    monkeypatch.setattr('agent.onboarding.is_seen', lambda *args: True)
    cli = HermesCLI.__new__(HermesCLI)
    cli.final_response_markdown = 'render'
    cli.busy_input_mode = mode
    cli._pending_input = Queue()
    cli._interrupt_queue = Queue()
    def accept(text):
        accepted.append(text)
        return True
    cli.agent = SimpleNamespace(steer=accept, redirect=accept, _supports_active_turn_redirect=True)
    text = '[bold]keep this literal[/bold]'
    cli._tui_enter_while_busy(text, [], text)
    if mode == 'queue':
        assert cli._pending_input.get_nowait() == text
    else:
        assert accepted == [text]
    output = Text.from_ansi('\n'.join(emitted)).plain
    assert output.startswith('  ' + label + '\n    ')
    assert text in output
    assert not any(mark in output for mark in ['⏩', '↪'])
    assert cli._interrupt_queue.empty()


def test_slash_queue_and_steer_use_same_layout_without_hiding_failure(monkeypatch):
    import cli as facade
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = HermesCLI.__new__(HermesCLI)
    cli.final_response_markdown = 'render'
    cli._pending_input = Queue()
    cli._agent_running = True
    cli.agent = SimpleNamespace(steer=lambda text: True)
    cli._cmd_queue('/queue Next task')
    cli._cmd_steer('/steer Focus here')
    assert cli._pending_input.get_nowait() == 'Next task'
    output = Text.from_ansi('\n'.join(emitted)).plain
    assert '  Queued for next turn\n    Next task' in output
    assert '  Steering queued after next tool call\n    Focus here' in output
    def fail(text):
        raise RuntimeError('example failure')
    cli.agent.steer = fail
    cli._cmd_steer('/steer Again')
    assert emitted[-1] == '  Steer failed: example failure'
