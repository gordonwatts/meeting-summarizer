from __future__ import annotations

from meeting_summarizer.markdown.common import (
    escape_table_cell,
    parse_markdown_table,
    render_markdown_table,
    unescape_table_cell,
)


def test_escape_and_unescape_table_cell_round_trip() -> None:
    value = "A|B\nC"
    assert unescape_table_cell(escape_table_cell(value)) == value


def test_render_and_parse_markdown_table_round_trip() -> None:
    lines = render_markdown_table(["A", "B"], [["one", "two"]])
    rows, index = parse_markdown_table(lines, 0)
    assert rows == [{"A": "one", "B": "two"}]
    assert index == len(lines)
