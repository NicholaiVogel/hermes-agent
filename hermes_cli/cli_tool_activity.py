"""Quiet tool activity for the readable Python CLI, separate from assistant prose."""
from io import StringIO

from rich.console import Console
from rich.text import Text


def render_tool_activity(summary: str, width: int, *, failed: bool = False) -> str:
    from hermes_cli.skin_engine import get_active_skin

    skin = get_active_skin()
    color = skin.get_color('ui_error' if failed else 'banner_dim', '#8B949E')
    text = Text.from_ansi(summary).plain
    # get_cute_tool_message's documented prefix is "┊ {emoji} {verb} {detail}".
    # Retain the useful summary and duration, replacing only its decoration.
    for tool_prefix in (skin.tool_prefix, '┊'):
        if tool_prefix and text.startswith(tool_prefix + ' '):
            parts = text[len(tool_prefix):].strip().split(maxsplit=1)
            text = parts[1] if len(parts) == 2 else text
            break
    if failed:
        text = 'Failed · ' + text
    buf = StringIO()
    console = Console(file=buf, width=max(1, width), height=25, force_terminal=True)
    content = Text(text, style=color)
    # Every wrapped row retains its indent and rail, including long command paths.
    prefix = '  │ ' if width >= 8 else '│ '
    for row in content.wrap(console, max(1, width - len(prefix))):
        console.print(Text(prefix, style=color) + row, overflow='crop')
    # A blank row separates the following assistant message from activity.
    return buf.getvalue().rstrip('\n') + '\n'


def print_tool_activity(summary: str, *, failed: bool = False) -> None:
    from cli import _cprint, _record_output_history_entry, _suspend_output_history

    def lines():
        from cli import _terminal_columns
        return render_tool_activity(summary, _terminal_columns(), failed=failed).split('\n')

    _record_output_history_entry(lines)
    with _suspend_output_history():
        _cprint('\n'.join(lines()))
