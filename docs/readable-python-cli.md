# Readable Markdown in the Python CLI

Enable the renderer in your existing config (merge these keys under `display`):

```yaml
display:
  final_response_markdown: render
  streaming: true
```

This changes the classic Python CLI, not `hermes --tui`. It uses the already installed
Rich and prompt-toolkit packages. No model messages, tool results or stored conversation
content are rewritten.

The last Markdown block is a live prompt-toolkit widget. Earlier blocks are committed
to normal scrollback. A Markdown parser keeps lists, tables and fenced code together;
unfinished paragraphs and code remain visible as tokens arrive. A tall unfinished block
shows its tail in at most half the terminal. Its full contents enter scrollback when
it completes. Approval and question panels temporarily hide the preview to retain room
for their controls.

Headings are left aligned, response boxes are omitted, and fenced code has syntax
highlighting without added indentation. Ordinary prose uses native terminal soft-wrap
when committed, preserving copy/paste as a single logical paragraph. Structured Markdown
(lists, tables and long code lines) uses Rich's width-aware layout. Source-backed output
history re-renders at the new width on redraw. `NO_COLOR` remains respected.

The existing `strip` and `raw` modes retain their old streaming behavior. Set
`display.final_response_markdown` back to `strip` and restart Hermes to disable this
renderer. Skin colors and branding remain configurable through the existing skin engine.

Verification uses `scripts/run_tests.sh tests/cli/test_readable_markdown_stream.py` plus
existing streaming, thinking-tag, output-history and transformed-response tests. The
interaction test runs a real prompt-toolkit application with a worker stream and typed
input. The implementation was also exercised through the complete CLI in a pseudo-terminal
with an offline response fixture at 90, 48 and 100 columns.

This is a local source change, not a supported renderer plugin. Keep the patch or feature
branch when updating Hermes; there is no automatic reapplication or monkey patch loader.
