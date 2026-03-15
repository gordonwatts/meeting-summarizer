from __future__ import annotations

from meeting_summarizer.models import FocusAreaReview


def render_focus_area_markdown(reviews: list[FocusAreaReview]) -> str:
    """Render focus-area reviews as markdown.

    Args:
        reviews: Focus-area reviews to serialize.

    Returns:
        Markdown content for the focus-area report.
    """
    lines = ["# Focus Area Cross Reference", ""]
    for review in reviews:
        lines.extend([f"## {review.focus_area.title}", ""])
        if review.mentioned_people:
            lines.append(f"People mentioned: {', '.join(review.mentioned_people)}")
            lines.append("")
        if review.relevant_points:
            lines.append("Relevant points:")
            lines.extend(f"- {item}" for item in review.relevant_points)
            lines.append("")
        if review.outstanding_questions:
            lines.append("Outstanding questions:")
            lines.extend(f"- {item}" for item in review.outstanding_questions)
            lines.append("")
        if review.action_items:
            lines.append("Action items:")
            lines.extend(f"- {item}" for item in review.action_items)
            lines.append("")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
