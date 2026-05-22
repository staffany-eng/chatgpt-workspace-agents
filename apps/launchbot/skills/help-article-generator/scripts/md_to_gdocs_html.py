#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert help article Markdown to Google Docs-friendly HTML."
    )
    parser.add_argument("--input", "-i", required=True, help="Input Markdown file path")
    parser.add_argument(
        "--output", "-o", required=True, help="Output HTML file path for Google Docs"
    )
    parser.add_argument("--title", "-t", default="", help="Optional HTML title")
    return parser.parse_args()


def parse_inline(text: str) -> str:
    out = html.escape(text)

    out = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: (
            f'<a href="{html.escape(m.group(2))}" target="_blank" '
            f'rel="noopener noreferrer">{m.group(1)}</a>'
        ),
        out,
    )
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def split_table_cells(row: str) -> list[str]:
    stripped = row.strip().removeprefix("|").removesuffix("|")
    return [cell.strip() for cell in stripped.split("|")]


def is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))


def close_list(parts: list[str], list_type: str | None) -> None:
    if list_type:
        parts.append(f"</{list_type}>")


def render_markdown(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    parts: list[str] = []
    list_type: str | None = None
    in_code = False
    code_buffer: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()

        if trimmed.startswith("```"):
            close_list(parts, list_type)
            list_type = None
            if in_code:
                parts.append(f"<pre><code>{html.escape(chr(10).join(code_buffer))}</code></pre>")
                code_buffer = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buffer.append(line)
            i += 1
            continue

        if not trimmed:
            close_list(parts, list_type)
            list_type = None
            i += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", trimmed)
        if heading_match:
            close_list(parts, list_type)
            list_type = None
            level = len(heading_match.group(1))
            parts.append(f"<h{level}>{parse_inline(heading_match.group(2))}</h{level}>")
            i += 1
            continue

        if (
            "|" in line
            and i + 1 < len(lines)
            and is_table_separator(lines[i + 1])
        ):
            close_list(parts, list_type)
            list_type = None
            header_cells = split_table_cells(line)
            i += 2
            row_cells: list[list[str]] = []
            while i < len(lines) and "|" in lines[i]:
                row_cells.append(split_table_cells(lines[i]))
                i += 1

            header_html = "".join(f"<th>{parse_inline(cell)}</th>" for cell in header_cells)
            rows_html = "".join(
                "<tr>"
                + "".join(f"<td>{parse_inline(cell)}</td>" for cell in cells)
                + "</tr>"
                for cells in row_cells
            )
            parts.append(
                f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>"
            )
            continue

        ul_match = re.match(r"^[-*]\s+(.+)$", trimmed)
        if ul_match:
            if list_type != "ul":
                close_list(parts, list_type)
                parts.append("<ul>")
                list_type = "ul"
            parts.append(f"<li>{parse_inline(ul_match.group(1))}</li>")
            i += 1
            continue

        ol_match = re.match(r"^\d+\.\s+(.+)$", trimmed)
        if ol_match:
            if list_type != "ol":
                close_list(parts, list_type)
                parts.append("<ol>")
                list_type = "ol"
            parts.append(f"<li>{parse_inline(ol_match.group(1))}</li>")
            i += 1
            continue

        close_list(parts, list_type)
        list_type = None
        if trimmed.startswith("> "):
            parts.append(f"<blockquote>{parse_inline(trimmed[2:])}</blockquote>")
        else:
            parts.append(f"<p>{parse_inline(trimmed)}</p>")
        i += 1

    if in_code and code_buffer:
        parts.append(f"<pre><code>{html.escape(chr(10).join(code_buffer))}</code></pre>")
    close_list(parts, list_type)
    return "\n".join(parts)


def default_title(markdown: str, input_path: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return Path(input_path).stem


def main() -> int:
    args = parse_args()
    source = Path(args.input).read_text(encoding="utf-8")
    title = args.title or default_title(source, args.input)
    body = render_markdown(source)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, 'Helvetica Neue', sans-serif; line-height: 1.55; color: #0e0e0e; margin: 28px; font-size: 12px; }}
    h1 {{ margin: 24px 0 12px; font-size: 24px; font-weight: 700; }}
    h2 {{ margin: 20px 0 10px; font-size: 18px; font-weight: 700; }}
    h3 {{ margin: 16px 0 8px; font-size: 15px; font-weight: 700; }}
    h4, h5, h6 {{ margin: 14px 0 6px; font-size: 12px; font-weight: 700; }}
    p {{ margin: 8px 0; }}
    ul, ol {{ margin: 8px 0 10px 24px; }}
    code {{ font-family: Menlo, Monaco, 'Courier New', monospace; background: #f5f5f5; padding: 1px 4px; border-radius: 4px; }}
    pre {{ background: #f7f7f7; padding: 12px; border-radius: 6px; overflow: auto; }}
    blockquote {{ margin: 8px 0; padding: 6px 10px; border-left: 4px solid #ddd; color: #555; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid #ccc; text-align: left; padding: 8px; vertical-align: top; }}
    th {{ background: #f3f3f3; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
    Path(args.output).write_text(html_doc, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
