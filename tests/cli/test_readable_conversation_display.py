"""User previews are literal and bounded; review notices retain details and ordering."""
from rich.text import Text

from cli import HermesCLI
from hermes_cli.cli_conversation_display import render_user_preview, render_review_notice


def test_user_preview_wraps_before_budget_and_keeps_literal_input(monkeypatch):
    monkeypatch.setenv('NO_COLOR', '1')
    short = '[bold]literal[/bold] **not Markdown**'
    output = render_user_preview(short, 80)
    assert short in output
    assert 'You' in output
    assert all(span.style.color is None for span in Text.from_ansi(output).spans)
    long = 'First words ' + 'middle words ' * 50 + 'last words'
    output = render_user_preview(long, 40, first=2, last=1, timestamp='12:34')
    assert 'First words' in output and 'last words' in output
    assert 'more lines' in output and '12:34' in output
    assert all(Text.from_ansi(row).cell_len <= 40 for row in output.splitlines())
    assert long.endswith('last words')


def test_review_notice_waits_for_assistant_and_preserves_all_details(monkeypatch):
    import cli as facade
    emitted = []
    monkeypatch.setattr(facade, '_cprint', emitted.append)
    cli = HermesCLI.__new__(HermesCLI)
    cli.final_response_markdown = 'render'
    cli.show_reasoning = False
    cli._reset_stream_state()
    cli._stream_delta('Assistant is still speaking.')
    detail = "Skill 'example' patched (SKILL.md) · Skill 'example' patched (references/guide.md)"
    cli._agent_status_print('  💾 Self-improvement review: ' + detail)
    assert not emitted
    cli._flush_stream()
    output = '\n'.join(emitted)
    assert output.index('Assistant is still speaking.') < output.index('Self-improvement review')
    for part in ('SKILL.md', 'references/guide.md'):
        assert part in output
    assert '💾' not in output
    cli._agent_status_print('WARNING: example failure')
    assert emitted[-1] == 'WARNING: example failure'
    assert all(Text.from_ansi(row).cell_len <= 30
               for row in render_review_notice(detail, 30).splitlines())
