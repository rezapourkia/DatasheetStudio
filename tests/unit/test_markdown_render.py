"""Unit tests for the minimal Markdown renderer."""

from datasheet_studio.ui.markdown_render import html_escape, markdown_to_html


def test_heading_bold_italic():
    html = markdown_to_html("# Title\n\nSome **bold** and *italic* text.")
    assert "<h1 style=" in html and ">Title</h1>" in html
    assert "<b>bold</b>" in html
    assert "<i>italic</i>" in html


def test_code_block_and_inline_code():
    html = markdown_to_html("Use `x = 1` here.\n\n```\ndef f():\n    return 1\n```")
    assert "<code style=" in html and ">x = 1</code>" in html
    assert "<pre style=" in html and "<code>" in html
    assert "def f():" in html


def test_lists():
    html = markdown_to_html("- one\n- two\n\n1. first\n2. second")
    assert "<ul>" in html and "<li>one</li>" in html
    assert "<ol>" in html and "<li>first</li>" in html


def test_table():
    html = markdown_to_html(
        "| Pin | Name |\n|---|---|\n| 1 | GND |\n| 2 | VDD |"
    )
    assert "<table" in html
    assert "<th style=" in html and ">Pin</th>" in html
    assert "<td style=" in html and ">GND</td>" in html


def test_links():
    html = markdown_to_html("[datasheet](https://example.com/a.pdf)")
    assert '<a href="https://example.com/a.pdf">datasheet</a>' in html


def test_blockquote_and_hr():
    html = markdown_to_html("> warning\n\n---")
    assert "<blockquote style=" in html and ">warning</blockquote>" in html
    assert "<hr>" in html


def test_html_escape():
    assert html_escape("<script>") == "&lt;script&gt;"
