"""The real CLI callback keeps unfinished Markdown visible and commits content once."""
import asyncio
from threading import Thread

from prompt_toolkit.application import Application
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import TextArea
from rich.text import Text

from cli import HermesCLI
from hermes_cli.cli_markdown_stream import preview_window, render_markdown


def make_cli():
    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = 'render'
    cli._reset_stream_state()
    return cli


def test_incremental_markdown_preserves_blocks_and_flushes_once(monkeypatch):
    import cli as facade
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = make_cli()
    source = '# Heading\n\n**Readable** prose.\n\n- item\n  - nested\n\n```python\ndef greet():\n    return 42\n```\n\n| Name | Value |\n| --- | --- |\n| Test | 42 |\n'
    for char in source:
        cli._stream_delta(char)
    stream = cli._markdown_stream
    assert 'Test' in '\n'.join(stream.preview(40))
    cli._flush_stream()
    output = '\n'.join(emitted)
    for word in ['Heading', 'Readable', 'nested', 'def greet():', 'return 42', 'Test']:
        assert output.count(word) == 1
    assert '\n    return 42' in output
    assert '**Readable**' not in output
    before = list(emitted)
    cli._flush_stream()
    assert emitted == before
    assert not stream.preview(40)
    assert "https://example.com" in render_markdown("[Example](https://example.com)", 80)
    paragraph = "Copy this paragraph without inserted line breaks. " * 8
    assert "\n" not in render_markdown(paragraph, 20, color=False, terminal_wrap=True)
    for width in [20, 40, 80]:
        lines = render_markdown(source, width, color=False).splitlines()
        assert all(Text.from_ansi(line).cell_len <= width for line in lines)


def test_live_worker_preview_input_resize_and_interruption(monkeypatch):
    import cli as facade
    committed = []
    monkeypatch.setattr(facade, '_pt_print_ansi', committed.append)

    async def worker(fn, *args):
        errors = []
        def run():
            try:
                fn(*args)
            except BaseException as error:
                errors.append(error)
        thread = Thread(target=run, daemon=True)
        thread.start()
        while thread.is_alive():
            await asyncio.sleep(.01)
        if errors:
            raise errors[0]

    async def exercise():
        cli = make_cli()
        with create_pipe_input() as pipe:
            editor = TextArea(prompt='> ')
            app = Application(layout=Layout(HSplit([preview_window(cli), editor]),
                                           focused_element=editor),
                              input=pipe, output=DummyOutput())
            cli._app = app
            task = asyncio.create_task(app.run_async(set_exception_handler=False))
            try:
                while not app.is_running:
                    if task.done():
                        await task
                    await asyncio.sleep(0)
                await worker(cli._stream_delta, '**Visible before newline**')
                assert 'Visible before newline' in '\n'.join(cli._markdown_stream.preview(40))
                assert not committed
                pipe.send_text('draft stays here')
                for _ in range(100):
                    if editor.text == 'draft stays here':
                        break
                    await asyncio.sleep(.01)
                assert editor.text == 'draft stays here'
                await worker(cli._stream_delta, '\n\n```python\n' + 'print(42)\n' * 30)
                for width in [20, 90, 40]:
                    content = app.layout.container.children[0].content.create_content(width, 8)
                    assert content.line_count > 8
                    assert content.cursor_position.y == content.line_count - 1
                    assert all(Text.from_ansi(line).cell_len <= width
                               for line in cli._markdown_stream.preview(width))
                cli._approval_state = {"command": "example"}
                assert app.layout.container.children[0].height().max == 0
                cli._approval_state = None
                # The same flush used by interruption/tools must retain an unfinished fence.
                await worker(cli._flush_stream)
                assert not cli._markdown_stream.pending
                assert '\n'.join(committed).count('Visible before newline') == 1
                assert '\n'.join(committed).count('print') == 30
                assert editor.text == 'draft stays here'
            finally:
                if app.is_running:
                    app.exit()
                await task
    asyncio.run(asyncio.wait_for(exercise(), timeout=10))
