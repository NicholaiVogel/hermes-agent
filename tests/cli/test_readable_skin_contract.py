"""The optional skin themes interface chrome; Markdown syntax retains its fixed theme."""
from rich.text import Text

from hermes_cli.cli_conversation_display import render_user_preview
from hermes_cli.cli_markdown_stream import render_markdown
from hermes_cli.cli_tool_activity import render_tool_activity
from hermes_cli.skin_engine import load_skin


def test_readable_skin_colors_interface_and_errors_without_recoloring_markdown(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.setenv('COLORTERM', 'truecolor')
    monkeypatch.setenv('TERM', 'xterm-256color')
    active = load_skin('readable-python')
    monkeypatch.setattr('hermes_cli.skin_engine.get_active_skin', lambda: active)
    source = '# Heading\n\nProse.\n\n```python\nreturn 42\n```'
    markdown = render_markdown(source, 80)
    user = render_user_preview('Hello', 80)
    tool = render_tool_activity('read note.md', 80)
    failed = render_tool_activity('read note.md', 80, failed=True)
    def colors(text):
        return {span.style.color.get_truecolor().hex for span in Text.from_ansi(text).spans
                if span.style.color is not None}
    assert '#e6e6e6' in colors(user)
    assert any(span.style.bgcolor and span.style.bgcolor.get_truecolor().hex == '#303030'
               for span in Text.from_ansi(user).spans)
    assert active.get_color('banner_dim').lower() in colors(tool)
    assert active.get_color('ui_error').lower() in colors(failed)
    assert 'Failed' in Text.from_ansi(failed).plain
    active = load_skin('default')
    assert render_markdown(source, 80) == markdown
    assert render_tool_activity('read note.md', 80) != tool
    monkeypatch.setenv('NO_COLOR', '1')
    assert not colors(render_markdown(source, 80))
    assert not colors(render_tool_activity('read note.md', 80, failed=True))
