"""Minimal Markdown -> HTML renderer used by the AI chat panel.

Supports the common constructs produced by chat models: headings, bold,
italic, inline code, fenced code blocks, unordered/ordered lists,
blockquotes, tables, links, and horizontal rules.
"""

import html
import re


def html_escape(text: str) -> str:
    """Escape text for safe inclusion in HTML."""
    return html.escape(text)


def _inline(text: str) -> str:
    """Apply inline markdown formatting (code, links, bold, italic)."""
    # inline code first so markdown inside code stays untouched
    text = re.sub(
        r"`([^`]+)`",
        lambda m: (
            "<code style='background:#eef1f4; border-radius:4px;"
            " padding:1px 5px; font-family:Consolas,Monaco,monospace;"
            " font-size:12px;'>"
            f"{html_escape(m.group(1))}</code>"
        ),
        text,
    )
    # links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}">{html_escape(m.group(1))}</a>',
        text,
    )
    # bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # italic (single asterisks not part of bold)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def markdown_to_html(text: str) -> str:
    """Convert markdown text to an HTML fragment for QTextBrowser."""
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    code_lines: list[str] = []
    in_list = False
    list_tag = "ul"
    i = 0

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{list_tag}>")
            in_list = False

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                in_code = False
                close_list()
                out.append(
                    "<pre style='background:#0d1117; color:#e6edf3;"
                    " padding:10px 12px; border-radius:8px; margin:6px 0;"
                    " font-family:Consolas,Monaco,monospace; font-size:12px;"
                    " line-height:1.5;'><code>"
                    + html_escape("\n".join(code_lines))
                    + "</code></pre>"
                )
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # table
        if line.strip().startswith("|"):
            close_list()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            out.append(
                "<table cellpadding='0' cellspacing='0' border='0' "
                "style='border-collapse:collapse; margin:6px 0; font-size:12.5px;'>"
            )
            for idx, tl in enumerate(table_lines):
                if re.match(r"^\|?[\s:\-|]+\|?$", tl):
                    continue
                cells = [c.strip() for c in tl.strip("|").split("|")]
                tag = "th" if idx == 0 else "td"
                style = (
                    "background:#eef1f5; font-weight:600; text-align:left;"
                    if idx == 0
                    else ""
                )
                out.append(
                    "<tr>"
                    + "".join(
                        f"<{tag} style='border:1px solid #d8dce3; padding:5px 10px; {style}'>"
                        f"{_inline(html_escape(c))}</{tag}>"
                        for c in cells
                    )
                    + "</tr>"
                )
            out.append("</table>")
            continue

        stripped = line.strip()
        if stripped == "":
            close_list()
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            out.append(
                f"<h{level} style='margin:10px 0 6px 0; line-height:1.35;'>"
                f"{_inline(html_escape(heading.group(2)))}</h{level}>"
            )
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_list()
            content = stripped.lstrip(">").strip()
            out.append(
                "<blockquote style='border-left:3px solid #d0d7de;"
                " margin:6px 0; padding:2px 12px; color:#57606a;'>"
                + _inline(html_escape(content))
                + "</blockquote>"
            )
            i += 1
            continue

        ul = re.match(r"^[-*+]\s+(.*)$", stripped)
        if ul:
            if not in_list or list_tag != "ul":
                close_list()
                out.append("<ul>")
                in_list = True
                list_tag = "ul"
            out.append(f"<li>{_inline(html_escape(ul.group(1)))}</li>")
            i += 1
            continue

        ol = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if ol:
            if not in_list or list_tag != "ol":
                close_list()
                out.append("<ol>")
                in_list = True
                list_tag = "ol"
            out.append(f"<li>{_inline(html_escape(ol.group(1)))}</li>")
            i += 1
            continue

        close_list()
        out.append(
            "<p style='margin:4px 0; line-height:1.55;'>"
            + _inline(html_escape(stripped))
            + "</p>"
        )
        i += 1

    if in_code:
        out.append(
            "<pre style='background:#0d1117; color:#e6edf3; padding:10px 12px;"
            " border-radius:8px; margin:6px 0; font-family:Consolas,Monaco,monospace;"
            " font-size:12px; line-height:1.5;'><code>"
            + html_escape("\n".join(code_lines))
            + "</code></pre>"
        )
    close_list()
    return "\n".join(out)
