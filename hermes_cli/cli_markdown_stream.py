"""Rich Markdown in the classic CLI, with prompt_toolkit owning all live drawing.

Only the last top-level block is mutable. It lives in the application layout;
older blocks are printed above it through run_in_terminal, never cursor escapes.
"""
from __future__ import annotations

import asyncio
from io import StringIO
from threading import RLock

from markdown_it import MarkdownIt
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.layout.dimension import Dimension
from rich.console import Console
from rich.markdown import CodeBlock, Heading, Markdown, Paragraph
from rich.syntax import Syntax
from rich.theme import Theme


class _Heading(Heading):
    LEVEL_ALIGN = dict.fromkeys(Heading.LEVEL_ALIGN, "left")


class _CodeBlock(CodeBlock):
    def __rich_console__(self, console, options):
        # No decorative padding: copying code must preserve its original indentation.
        yield Syntax(str(self.text).rstrip("\n"), self.lexer_name, theme=self.theme,
                     word_wrap=True, padding=0, background_color="default")


class ReadableMarkdown(Markdown):
    elements = {**Markdown.elements, "heading_open": _Heading,
                "fence": _CodeBlock, "code_block": _CodeBlock}


class _TerminalParagraph(Paragraph):
    @classmethod
    def create(cls, markdown, token):
        # Only top-level prose can use terminal soft wrapping; nested lists need hanging indents.
        return (cls if token.level == 0 else Paragraph)(justify="left")

    def __rich_console__(self, console, options):
        yield from console.render(self.text, options.update(no_wrap=True, overflow="ignore"))


class _ScrollbackMarkdown(ReadableMarkdown):
    elements = {**ReadableMarkdown.elements, "paragraph_open": _TerminalParagraph}


def render_markdown(source: str, width: int, *, color: bool = True,
                    terminal_wrap: bool = False) -> str:
    """Share formatting; scrollback lets the terminal soft-wrap top-level prose."""
    from cli import _rich_text_from_ansi, _preserve_windows_dot_segments_for_markdown

    source = _preserve_windows_dot_segments_for_markdown(_rich_text_from_ansi(source).plain)
    buf = StringIO()
    console = Console(file=buf, width=max(1, width), height=25, force_terminal=color,
                      color_system="truecolor" if color else None,
                      theme=Theme({"markdown.h1": "bold", "markdown.h2": "bold",
                                   "markdown.h3": "bold", "markdown.code": "bold cyan"}))
    markdown = _ScrollbackMarkdown if terminal_wrap else ReadableMarkdown
    console.print(markdown(source, code_theme="github-dark", justify="left", hyperlinks=False), crop=False)
    return buf.getvalue().rstrip("\n")


class MarkdownStream:
    def __init__(self, cli):
        self.cli = cli
        self.pending = ""
        self._lock = RLock()
        self._parser = MarkdownIt().enable("table").enable("strikethrough")
        self._cache = None

    def preview(self, width: int) -> list[str]:
        with self._lock:
            key = (self.pending, width)
            if self._cache is None or self._cache[0] != key:
                lines = render_markdown(self.pending, width).splitlines() if self.pending else []
                self._cache = key, lines
            return self._cache[1]

    def feed(self, text: str, *, final: bool = False) -> None:
        """Callbacks arrive from the agent worker; finish printing before it emits tool status."""
        app = getattr(self.cli, "_app", None)
        if app is None or not app.is_running:
            self._update(text, final, live=False)
            return

        async def update():
            from prompt_toolkit.application import run_in_terminal
            with self._lock:
                source = self.pending + text
                cut = len(source) if final else self._stable_prefix(source)
            if cut:
                # Remove the preview and commit it while the layout is hidden.
                await run_in_terminal(lambda: self._update(text, final, live=True))
            else:
                # Tokens only invalidate the existing layout; do not hide/redraw the prompt.
                with self._lock:
                    self.pending = source
            app.invalidate()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is app.loop:
            app.create_background_task(update())
        else:
            asyncio.run_coroutine_threadsafe(update(), app.loop).result()

    def _update(self, text: str, final: bool, *, live: bool) -> None:
        from cli import _cprint, _record_output_history_entry, _suspend_output_history
        with self._lock:
            self.pending += text
            cut = len(self.pending) if final else self._stable_prefix(self.pending)
            committed, self.pending = self.pending[:cut], self.pending[cut:]
        if committed.strip():
            def lines(source=committed):
                from cli import _terminal_columns
                return (render_markdown(source, _terminal_columns(), terminal_wrap=True) + "\n").split("\n")
            # Retain source, not width-specific ANSI, so Ctrl+L/resize can reflow it.
            _record_output_history_entry(lines)
            with _suspend_output_history():
                if live:
                    from cli import _pt_print_ansi
                    _pt_print_ansi("\n".join(lines()))
                else:
                    from cli import _terminal_columns
                    import sys
                    rendered = render_markdown(committed, _terminal_columns(),
                                               color=sys.stdout.isatty(), terminal_wrap=True)
                    _cprint(rendered + "\n")

    def _stable_prefix(self, source: str) -> int:
        # Keep the last block: a paragraph can turn into a setext heading/table; a list,
        # quote or fence can continue across blank lines. Markdown's parser owns that grammar.
        tokens = self._parser.parse(source)
        starts = [t.map[0] for t in tokens if t.level == 0 and t.map and t.nesting != -1]
        if len(starts) < 2:
            return 0
        return sum(len(line) for line in source.splitlines(keepends=True)[:starts[-1]])


class _PreviewControl(UIControl):
    def __init__(self, cli):
        self.cli = cli

    def _lines(self, width):
        stream = getattr(self.cli, "_markdown_stream", None)
        return stream.preview(width) if stream else []

    def preferred_height(self, width, max_available_height, wrap_lines, get_line_prefix):
        return min(len(self._lines(width)), max_available_height)

    def create_content(self, width, height):
        lines = self._lines(width)
        fragments = [to_formatted_text(ANSI(line)) for line in lines]
        return UIContent(get_line=lambda i: fragments[i] if i < len(fragments) else [], line_count=len(lines),
                         cursor_position=Point(x=0, y=max(0, len(lines)-1)), show_cursor=False)


def preview_window(cli):
    from prompt_toolkit.application import get_app

    def height():
        # Approval and question widgets already budget the screen; give them their rows back.
        modal_states = ("_approval_state", "_clarify_state", "_sudo_state", "_secret_state",
                        "_slash_confirm_state", "_model_picker_state", "_command_palette_state")
        if any(getattr(cli, name, None) for name in modal_states):
            return Dimension.exact(0)
        return Dimension(min=0, max=max(1, get_app().output.get_size().rows // 2))

    return Window(_PreviewControl(cli), wrap_lines=False, always_hide_cursor=True, height=height)
