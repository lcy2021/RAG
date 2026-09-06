"""Markdown heading split used to keep chapter semantics intact."""

from __future__ import annotations

import re

_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+)$")


def split_by_heading(text: str) -> list[dict[str, str]]:
    """Split on ATX headings. Preamble before the first heading is one section."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        cleaned = text.strip()
        return [{"title": "", "content": cleaned}] if cleaned else []
    sections: list[dict[str, str]] = []
    first = matches[0]
    preamble = text[: first.start()].strip()
    if preamble:
        sections.append({"title": "", "content": preamble})
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        title = match.group(2).strip()
        content = f"{title}\n\n{body}".strip() if body else title
        sections.append({"title": title, "content": content})
    return sections
