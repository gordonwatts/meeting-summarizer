from __future__ import annotations

from meeting_summarizer.models import FocusAreaReview


def render_focus_area_markdown(reviews: list[FocusAreaReview]) -> str:
    lines = ["# Focus Area Cross Reference", ""]
    for review in reviews:
        lines.extend(
            [
                f"## {review.focus_area.title}",
                "",
                review.coverage_note,
                "",
                "Relevant points:",
            ]
        )
        lines.extend(f"- {item}" for item in review.relevant_points or ["None noted."])
        lines.extend(["", "Outstanding questions:"])
        lines.extend(
            f"- {item}" for item in review.outstanding_questions or ["None noted."]
        )
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in review.action_items or ["None noted."])
        lines.extend(["", "Quotes:"])
        lines.extend(f'- "{item}"' for item in review.quotes or ["None noted."])
        lines.append("")
    return "\n".join(lines).strip() + "\n"
