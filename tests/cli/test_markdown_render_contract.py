"""Final Rich output and streamed blocks share Markdown semantics at token edges."""
from io import StringIO

import pytest
from rich.console import Console
from rich.text import Text

from cli import HermesCLI, _render_final_assistant_content
from hermes_cli.cli_markdown_stream import assistant_label, render_markdown


CASES = [
    'Pipe prose: alpha | beta.\n\nNext paragraph.\n',
    'Name | Value\n--- | ---\nalpha | beta\n\nAfter table.\n',
    '~~~python\nprint("alpha")\n~~~\n\nAfter code.\n',
    '````text\n```literal```\n````\n\nAfter code.\n',
    'Setext heading\n==============\n\nBody.\n',
    '> quoted\nlazy continuation\n> > nested quote\n\nAfter quote.\n',
    'Read [the docs][docs].\n\nAnother paragraph.\n\n[docs]: https://example.com\n',
    'Exactly one trailing newline.\n',
]


@pytest.mark.parametrize('source', CASES)
@pytest.mark.parametrize('width', [20, 80])
def test_stream_and_final_renderable_preserve_same_content(monkeypatch, source, width):
    import cli as facade
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr(facade, '_terminal_columns', lambda: width)
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = 'render'
    cli._reset_stream_state()
    for character in source:
        cli._stream_delta(character)
    cli._flush_stream()
    streamed = Text.from_ansi('\n'.join(emitted)).plain
    buf = StringIO()
    Console(file=buf, width=width, height=25, color_system=None).print(
        _render_final_assistant_content(source, width=width, terminal_wrap=True), crop=False)
    label = Text.from_ansi(assistant_label(width, color=False)).plain.split()
    assert streamed.split() == label + buf.getvalue().split()
    assert label + render_markdown(source, width, color=False, terminal_wrap=True).split() == streamed.split()
    before = list(emitted)
    cli._flush_stream()
    assert emitted == before
