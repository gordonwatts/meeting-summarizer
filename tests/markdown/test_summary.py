from __future__ import annotations

from meeting_summarizer.markdown.summary import (
    parse_summary_markdown,
    render_summary_markdown,
)
from meeting_summarizer.models import (
    ActionItem,
    ExternalResource,
    MeetingSummary,
    SummaryTheme,
    TalkPoint,
)


def test_render_summary_markdown_outputs_expected_sections() -> None:
    summary = MeetingSummary(
        paragraph="The meeting covered tracking and operations.",
        themes=[SummaryTheme(title="tracking", details=["operations"])],
        action_items=[
            ActionItem(
                mentioner="Alice", description="Follow up", quote="I'll follow up."
            )
        ],
        resources=[
            ExternalResource(
                name="example.com", resource_type="link", context="Background reading"
            )
        ],
        talk_points=[
            TalkPoint(
                speaker="Alice",
                salient_points=["Point"],
                questions=["Question"],
                quotes=["Quote"],
            )
        ],
    )
    summary_markdown = render_summary_markdown(summary)
    assert "# Meeting Summary" in summary_markdown
    assert "## Themes" in summary_markdown
    assert "- tracking" in summary_markdown
    assert "| Theme | Details |" not in summary_markdown
    assert "| Owner | Action | Quote |" in summary_markdown
    assert "| Resource | Type | Context |" in summary_markdown


def test_parse_summary_markdown_supports_legacy_theme_table() -> None:
    content = """# Meeting Summary

The meeting covered tracking and operations.

## Themes

| Theme | Details |
| --- | --- |
| tracking | operations |

## Action Items

| Owner | Action | Quote |
| --- | --- | --- |
| None noted. |  |  |

## External Resources

| Resource | Type | Context |
| --- | --- | --- |
| None noted. |  |  |

## Talk Highlights
"""

    parsed = parse_summary_markdown(content)
    assert parsed.themes == [SummaryTheme(title="tracking", details=["operations"])]


def test_parse_summary_markdown_round_trips_summary() -> None:
    summary = MeetingSummary(
        paragraph="The meeting covered tracking and operations.",
        themes=[SummaryTheme(title="tracking")],
        action_items=[
            ActionItem(
                mentioner="Alice", description="Follow up", quote="I'll follow up."
            )
        ],
        resources=[
            ExternalResource(
                name="example.com", resource_type="link", context="Background reading"
            )
        ],
        talk_points=[
            TalkPoint(
                speaker="Alice",
                salient_points=["Point"],
                questions=["Question"],
                quotes=["Quote"],
            )
        ],
    )
    assert parse_summary_markdown(render_summary_markdown(summary)) == summary


def test_render_summary_markdown_omits_empty_question_sections() -> None:
    summary = MeetingSummary(
        paragraph="Paragraph.",
        themes=[],
        action_items=[],
        resources=[],
        talk_points=[
            TalkPoint(
                speaker="Alice",
                salient_points=["Point"],
                questions=[],
                quotes=[],
            )
        ],
    )

    summary_markdown = render_summary_markdown(summary)
    assert "Questions:" not in summary_markdown
