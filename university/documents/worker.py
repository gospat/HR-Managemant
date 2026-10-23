"""Bounded plain-document renderer: HTML text/tables only; no resource resolver."""

import io
from pathlib import Path
import resource
import sys
from xml.sax.saxutils import escape


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    from bs4 import BeautifulSoup, NavigableString, Tag
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        LongTable,
        TableStyle,
    )

    raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    html = raw.decode("utf-8")
    if len(html.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Document too large")
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(
        [
            "script",
            "style",
            "head",
            "iframe",
            "object",
            "embed",
            "svg",
            "form",
            "template",
        ]
    ):
        node.decompose()
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.is_file():
        raise ValueError("Required Unicode export font is not installed")
    pdfmetrics.registerFont(TTFont("DocumentSans", str(font)))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "DocumentSans"
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 13
    story = []
    characters = 0

    def paragraph(text, style="BodyText"):
        nonlocal characters
        text = " ".join(text.split())
        characters += len(text)
        if characters > 200000:
            raise ValueError("Document text exceeds export limit")
        return Paragraph(escape(text), styles[style])

    def visit(node):
        if isinstance(node, NavigableString):
            if node.strip():
                story.append(paragraph(str(node)))
            return
        if not isinstance(node, Tag):
            return
        if node.name == "table":
            rows = []
            for row in node.find_all("tr"):
                if row.find_parent("table") != node:
                    continue
                cells = row.find_all(["th", "td"], recursive=False)
                if cells:
                    if len(cells) > 12 or len(rows) >= 1000:
                        raise ValueError("Table exceeds export limit")
                    rows.append(
                        [paragraph(cell.get_text(" ", strip=True)) for cell in cells]
                    )
            if rows:
                columns = max(map(len, rows))
                for row in rows:
                    row.extend([""] * (columns - len(row)))
                table = LongTable(
                    rows,
                    colWidths=[(A4[0] - 72) / columns] * columns,
                    hAlign="LEFT",
                    splitByRow=True,
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            (
                                "LINEBELOW",
                                (0, 0),
                                (-1, -1),
                                0.25,
                                colors.HexColor("#d1d5db"),
                            ),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 10)])
            return
        if node.name in {"p", "h1", "h2", "h3", "li", "dt", "dd", "pre", "blockquote"}:
            text = node.get_text(" ", strip=True)
            if text:
                style = (
                    "Heading1"
                    if node.name == "h1"
                    else "Heading2" if node.name in {"h2", "h3"} else "BodyText"
                )
                story.extend([paragraph(text, style), Spacer(1, 6)])
            return
        for child in node.children:
            visit(child)

    visit(soup.body or soup)
    if not story:
        raise ValueError("Document has no printable content")
    output = io.BytesIO()

    def page(canvas, document):
        if document.page > 100:
            raise ValueError("Document exceeds page limit")
        canvas.setFont("DocumentSans", 8)
        canvas.drawRightString(A4[0] - 36, 20, str(document.page))

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="HR document",
        author="Bells University of Technology",
    )
    document.build(story, onFirstPage=page, onLaterPages=page)
    result = output.getvalue()
    if len(result) > 10 * 1024 * 1024:
        raise ValueError("Export too large")
    sys.stdout.buffer.write(result)


if __name__ == "__main__":
    main()
