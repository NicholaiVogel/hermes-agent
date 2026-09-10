# Readable Markdown in the Python CLI

Enable the renderer in your existing config (merge these keys under `display`):

```yaml
display:
  final_response_markdown: render
  streaming: true
  skin: readable-python  # optional; other skins also work
```

This changes the classic Python CLI, not `hermes --tui`. It uses the already installed
Rich and prompt-toolkit packages. No model messages, tool results or stored conversation
content are rewritten.

The last Markdown block is a live prompt-toolkit widget. Earlier blocks are committed
to normal scrollback. A Markdown parser keeps lists, tables and fenced code together;
unfinished paragraphs and code remain visible as tokens arrive. A tall unfinished block
shows its tail in at most half the terminal. Above 8 KiB of pending source, the preview
uses a bounded literal tail to keep typing responsive; full Markdown formatting returns
on commit. Reference-style links conservatively keep their document context until flush. Its full contents enter scrollback when
it completes. Approval and question panels temporarily hide the preview to retain room
for their controls.

Headings are left aligned, response boxes are omitted, and fenced code has syntax
highlighting without added indentation. Ordinary prose uses native terminal soft-wrap
when committed, preserving copy/paste as a single logical paragraph. Structured Markdown
(lists, tables and long code lines) uses Rich's width-aware layout. Source-backed output
history re-renders at the new width on redraw. `NO_COLOR` remains respected.

Tool activity uses an indented, muted rail on every wrapped line, followed by a blank
line before assistant prose resumes. Failed tools retain an explicit `Failed` label
and the skin error color. Tool summaries and durations remain visible; history redraw
reflows the activity to the current terminal width.

User turns use a small **You** label and literal, regular-weight text at a maximum
88-column measure. The existing first/last-line preview settings apply after wrapping,
so long pasted paragraphs stay compact; full submitted content is unchanged. Successful
native image routing no longer repeats the attachment count or transport details.
Self-improvement review notices use muted, indented details and retain their position
after any active assistant response.

The existing `strip` and `raw` modes retain their old streaming behavior. Set
`display.final_response_markdown` back to `strip` and restart Hermes to disable this
renderer. Skin colors and branding remain configurable through the existing skin engine.

Verification uses `scripts/run_tests.sh tests/cli/test_readable_markdown_stream.py` plus
existing streaming, thinking-tag, output-history and transformed-response tests. The
interaction test runs a real prompt-toolkit application with a worker stream and typed
input. The implementation was also exercised through the complete CLI in a pseudo-terminal
with an offline response fixture at 90, 48 and 100 columns.

The renderer is integrated into the Python CLI; the optional `readable-python` skin uses
the existing skin engine. No new dependencies or model prompt instructions are required.

Rendering contract: `_render_final_assistant_content()` is the shared factory entry point
for completed output, streaming output and command views. Its render mode delegates to
`make_markdown()` for ANSI/path/table normalization and the Rich renderable. `print_markdown()`
commits complete source with reflowable history; `MarkdownStream` only manages pending
source and live presentation. The strip/raw branches retain their existing behavior.
Parameterized tests compare final renderables with character-by-character streaming for
pipes, pipe-less tables, backtick/tilde fences, setext headings, blockquotes, reference
links and trailing newlines. An event-loop test covers rapid worker deltas and tool events.

The optional `readable-python` skin is intended as a supported built-in, independently
selectable from Markdown rendering. It themes CLI labels, status, tools and errors.
Markdown prose/headings currently use the renderer's styles, and code uses `github-dark`;
switching skins does not change syntax highlighting. Full Markdown skin integration is
a separate concern, overlapping upstream PR #83236. Tests enforce this current boundary
and verify color-free fallback rather than claiming skin-aware syntax highlighting.
