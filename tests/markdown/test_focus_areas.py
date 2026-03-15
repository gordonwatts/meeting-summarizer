from __future__ import annotations

from meeting_summarizer.markdown.focus_areas import render_focus_area_markdown
from meeting_summarizer.models import FocusArea, FocusAreaReview


def test_render_focus_area_markdown_outputs_heading() -> None:
    review = FocusAreaReview(
        focus_area=FocusArea(id="tracking", title="Tracking", description="desc"),
        relevant_points=["Point"],
        outstanding_questions=["Question"],
        action_items=["Follow up"],
        quotes=["Quote"],
        coverage_note="Covered in detail.",
    )
    assert "# Focus Area Cross Reference" in render_focus_area_markdown([review])
