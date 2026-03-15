from __future__ import annotations

from meeting_summarizer.markdown.focus_areas import render_focus_area_markdown
from meeting_summarizer.models import FocusArea, FocusAreaReview


def test_render_focus_area_markdown_outputs_heading() -> None:
    review = FocusAreaReview(
        focus_area=FocusArea(id="tracking", title="Tracking", description="desc"),
        mentioned_people=["Alice", "Bob"],
        relevant_points=["Alice: Point"],
        outstanding_questions=["Bob: Question"],
        action_items=["Alice: Follow up"],
        quotes=["Quote"],
        coverage_note="Covered in detail.",
    )
    markdown = render_focus_area_markdown([review])
    assert "# Focus Area Cross Reference" in markdown
    assert "People mentioned: Alice, Bob" in markdown
    assert "Covered in detail." not in markdown
    assert "Quotes:" not in markdown
