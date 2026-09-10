"""Readable user turns and background review notices for the Python CLI."""
from io import StringIO

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich import box


def _console(width):
    return Console(file=StringIO(), width=max(1, min(width, 88)), height=25,
                   force_terminal=True)


def render_user_preview(text, width, *, first=2, last=2, timestamp=''):
    from hermes_cli.skin_engine import get_active_skin
    skin = get_active_skin()
    console = _console(width)
    # Wrap before applying the existing preview budget: one long pasted paragraph
    # must not bypass it. Only the displayed preview is shortened, never model input.
    rows = list(Text(text).wrap(console, max(1, console.width - 4)))
    first, last = max(1, first), max(0, last)
    if len(rows) > first + last:
        hidden = len(rows) - first - last
        rows = rows[:first] + [Text(f'… (+{hidden} more lines)',
                                  style=skin.get_color('banner_dim', '#8B949E'))] + (rows[-last:] if last else [])
    body = Text('\n').join(rows)
    console.print(Panel(
        body, box=box.ROUNDED, padding=(0, 1),
        border_style=skin.get_color('input_rule', '#58616A'),
        style=skin.get_color('banner_text', '#c9d1d9') + ' on ' + skin.get_color('status_bar_bg', '#1F1F1F'),
        subtitle=Text(timestamp) if timestamp else None, subtitle_align='right'))
    return console.file.getvalue().rstrip('\n') + '\n'


def render_review_notice(text, width):
    from hermes_cli.skin_engine import get_active_skin
    color = get_active_skin().get_color('banner_dim', '#8B949E')
    console = _console(width)
    console.print(Text('  Self-improvement review', style='bold ' + color))
    # Preserve all action details, with natural wrapping instead of one dense banner.
    for detail in text.split(' · '):
        for row in Text(detail, style=color).wrap(console, max(1, console.width - 4)):
            console.print(Text('    ', style=color) + row)
    console.print()
    return console.file.getvalue().rstrip('\n') + '\n'


def print_reflowing(render):
    from cli import _cprint, _record_output_history_entry, _suspend_output_history
    def lines():
        from cli import _terminal_columns
        return render(_terminal_columns()).split('\n')
    _record_output_history_entry(lines)
    with _suspend_output_history():
        _cprint('\n'.join(lines()))


def print_review_notice(text):
    prefix = '💾 Self-improvement review: '
    if not text.strip().startswith(prefix):
        return False
    details = text.strip()[len(prefix):]
    print_reflowing(lambda width: render_review_notice(details, width))
    return True
