"""Streaming preserves document-wide links and narrow-terminal table values."""
import pytest

from cli import HermesCLI
from hermes_cli.cli_markdown_stream import render_markdown


@pytest.mark.parametrize('source', [
    '[docs]: https://example.com\n\nIntro.\n\nRead [the docs][docs].\n',
    'Read [the docs][docs].\n\nAnother paragraph.\n\n[docs]: https://example.com\n',
    'Read [docs].\n\nAnother paragraph.\n\n[docs]: https://example.com\n',
])
def test_stream_reference_links_keep_document_context(monkeypatch, source):
    import cli as facade
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = 'render'
    cli._reset_stream_state()
    for character in source:
        cli._stream_delta(character)
    cli._flush_stream()
    output = '\n'.join(emitted)
    assert output.count('https://example.com') == 1
    assert '[docs]' not in output
    assert output.count('Read') == 1
    cli._flush_stream()
    assert '\n'.join(emitted) == output


def test_narrow_table_preserves_values_in_preview_final_and_replay(monkeypatch):
    import cli as facade
    cells = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta']
    source = ('| A | B | C | D | E | F | G | H |\n'
              '| --- | --- | --- | --- | --- | --- | --- | --- |\n'
              '| ' + ' | '.join(cells) + ' |\n')
    emitted, history = [], []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    monkeypatch.setattr(facade, '_record_output_history_entry', history.append)
    monkeypatch.setattr(facade, '_terminal_columns', lambda: 20)
    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = 'render'
    cli._reset_stream_state()
    cli._stream_delta(source)
    preview = '\n'.join(cli._markdown_stream.preview(20))
    cli._flush_stream()
    for output in [preview, '\n'.join(emitted), '\n'.join(history[0]()),
                   render_markdown(source, 20, color=False)]:
        for value in cells:
            assert value in output
