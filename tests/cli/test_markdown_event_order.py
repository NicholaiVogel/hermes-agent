"""Worker deltas and tool notifications share the real prompt-toolkit output queue."""
import asyncio
from threading import Thread
from types import SimpleNamespace

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import fragment_list_to_text, to_formatted_text
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import TextArea

from agent.codex_runtime import make_codex_app_server_event_bridge
from cli import HermesCLI
from hermes_cli.cli_markdown_stream import preview_window


def test_worker_markdown_boundary_and_tool_output_keep_event_order(monkeypatch):
    import cli as facade

    emitted = []
    # Capture only the terminal sink: _cprint and run_in_terminal retain their real
    # scheduling, so a queued tool line must compete with the next Markdown commit.
    monkeypatch.setattr(facade, '_pt_print', lambda value, **kwargs: emitted.append(
        fragment_list_to_text(to_formatted_text(value))))

    async def exercise():
        cli = HermesCLI.__new__(HermesCLI)
        cli.show_reasoning = False
        cli.final_response_markdown = 'render'
        cli.tool_progress_mode = 'all'
        cli._pending_tool_info = {}
        cli._last_scrollback_tool = None
        cli._turn_summary_record = lambda *args: None
        cli._reset_stream_state()
        errors = []
        with create_pipe_input() as pipe:
            editor = TextArea(prompt='> ')
            app = Application(layout=Layout(HSplit([preview_window(cli), editor]),
                                           focused_element=editor),
                              input=pipe, output=DummyOutput())
            cli._app = app
            cli._invalidate = lambda *args, **kwargs: app.invalidate()
            bridge = make_codex_app_server_event_bridge(SimpleNamespace(
                _fire_stream_delta=cli._stream_delta,
                tool_progress_callback=cli._on_tool_progress))

            def delta(text):
                bridge({'method': 'item/agentMessage/delta', 'params': {'delta': text}})

            def stream():
                try:
                    # No sleeps between deltas/events: the callback's own handoff
                    # must preserve order across stable-block and tool boundaries.
                    for chunk in ['**First', ' block.**', '\n', '\n', 'Before ', 'tool.', '\n']:
                        delta(chunk)
                    item = {'id': 'order-tool', 'type': 'commandExecution',
                            'command': 'cat event-order-note.md', 'aggregatedOutput': 'ok',
                            'exitCode': 0, 'durationMs': 1}
                    for method in ['item/started', 'item/completed']:
                        bridge({'method': method, 'params': {'item': item}})
                    for chunk in ['After ', 'tool.', '\n', '\n', 'Last ', 'block.', '\n']:
                        delta(chunk)
                    cli._flush_stream()
                    cli._flush_stream()
                except BaseException as error:
                    errors.append(error)

            task = asyncio.create_task(app.run_async(set_exception_handler=False))
            try:
                while not app.is_running:
                    if task.done():
                        await task
                    await asyncio.sleep(0)
                pipe.send_text('draft typed during streaming')
                worker = Thread(target=stream, daemon=True)
                worker.start()
                while worker.is_alive():
                    await asyncio.sleep(.01)
                if errors:
                    raise errors[0]
                while editor.text != 'draft typed during streaming':
                    await asyncio.sleep(.01)
                output = '\n'.join(emitted)
                markers = ['First block.', 'Before tool.', 'exec_comm', 'After tool.', 'Last block.']
                positions = [output.index(marker) for marker in markers]
                assert positions == sorted(positions)
                assert all(output.count(marker) == 1 for marker in markers)
                assert not cli._markdown_stream.pending
                assert editor.text == 'draft typed during streaming'
            finally:
                if app.is_running:
                    app.exit()
                await task

    asyncio.run(asyncio.wait_for(exercise(), timeout=10))
