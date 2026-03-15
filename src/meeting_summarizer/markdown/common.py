from __future__ import annotations


def escape_table_cell(value: str | None) -> str:
    """Escape a markdown table cell for safe rendering."""
    if not value:
        return ""
    return value.replace("|", "\\|").replace("\n", "<br>")


def unescape_table_cell(value: str) -> str:
    """Reverse markdown table escaping for parsed cell values."""
    return value.replace("<br>", "\n").replace("\\|", "|").strip()


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a simple markdown table as a list of lines.

    Args:
        headers: Table column headers.
        rows: Table row values in header order.

    Returns:
        Markdown lines representing the table.
    """
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    if not rows:
        lines.append(
            "| "
            + " | ".join(
                "None noted." if index == 0 else "" for index, _ in enumerate(headers)
            )
            + " |"
        )
        return lines
    for row in rows:
        lines.append("| " + " | ".join(escape_table_cell(cell) for cell in row) + " |")
    return lines


def parse_markdown_table(
    lines: list[str], start_index: int
) -> tuple[list[dict[str, str]], int]:
    """Parse a markdown table starting at the given line index.

    Args:
        lines: Full markdown content split into lines.
        start_index: Index of the table header line.

    Returns:
        Parsed row dictionaries and the first index after the table.
    """
    header_line = lines[start_index].strip()
    divider_line = lines[start_index + 1].strip()
    if not (header_line.startswith("|") and divider_line.startswith("|")):
        raise ValueError("Expected markdown table.")

    headers = [unescape_table_cell(cell) for cell in header_line.strip("|").split("|")]
    rows: list[dict[str, str]] = []
    index = start_index + 2
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("|"):
            break
        cells = [unescape_table_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells)))
        index += 1
    return rows, index
