#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path
from typing import Iterable, Sequence

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    ListFlowable,
    ListItem,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents


INK = colors.HexColor("#16211f")
FOREST = colors.HexColor("#12372f")
TEAL = colors.HexColor("#007f8b")
AMBER = colors.HexColor("#d58a00")
MUTED = colors.HexColor("#5c6a66")
RULE = colors.HexColor("#d7e2df")
PAPER = colors.white
SOFT = colors.HexColor("#f3f7f6")
DEEP = colors.HexColor("#0b241f")
AUTHOR = "Siddharth Nilesh Patel"
AFFILIATION = "Independent Researcher"
FULL_TITLE = "Universal Reduction Plane: A Compatibility-First Control Plane for Reducing Data and AI Waste"
ARTICLE_LICENSE = "CC BY 4.0"
SOFTWARE_LICENSE = "Apache-2.0"
FONT_REGULAR = "URP-Vera"
FONT_BOLD = "URP-Vera-Bold"
FONT_ITALIC = "URP-Vera-Italic"
FONT_BOLD_ITALIC = "URP-Vera-BoldItalic"


def register_fonts() -> None:
    font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(font_dir / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(font_dir / "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(font_dir / "VeraIt.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD_ITALIC, str(font_dir / "VeraBI.ttf")))
    pdfmetrics.registerFontFamily(
        "URP-Vera",
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_ITALIC,
        boldItalic=FONT_BOLD_ITALIC,
    )


class WhitePaperDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs: object) -> None:
        super().__init__(filename, **kwargs)
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="publication", frames=[frame], onPage=self._decorate_page))

    def afterFlowable(self, flowable: Flowable) -> None:
        if not isinstance(flowable, Paragraph) or flowable.style.name != "Heading2":
            return
        title = flowable.getPlainText()
        key = f"section-{self.seq.nextf('section')}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=0, closed=False)
        self.notify("TOCEntry", (0, title, self.page, key))

    def _decorate_page(self, canvas: object, doc: object) -> None:
        canvas.saveState()
        canvas.setTitle(FULL_TITLE)
        canvas.setAuthor(AUTHOR)
        canvas.setCreator("URP publication renderer")
        canvas.setSubject("A compatibility-first control plane for reducing data and AI waste")
        canvas.setKeywords("URP, data reduction, AI infrastructure, exact cache, FinOps, S3 gateway")
        if doc.page > 1:
            page_width, page_height = A4
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.6)
            canvas.line(doc.leftMargin, page_height - 17 * mm, page_width - doc.rightMargin, page_height - 17 * mm)
            canvas.setFont(FONT_BOLD, 7.5)
            canvas.setFillColor(FOREST)
            canvas.drawString(doc.leftMargin, page_height - 13 * mm, "UNIVERSAL REDUCTION PLANE")
            canvas.setFont(FONT_REGULAR, 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(page_width - doc.rightMargin, page_height - 13 * mm, "TECHNICAL REPORT 1.0")
            canvas.line(doc.leftMargin, 15 * mm, page_width - doc.rightMargin, 15 * mm)
            canvas.drawString(doc.leftMargin, 10 * mm, "github.com/thewisecrab/urp")
            canvas.drawRightString(page_width - doc.rightMargin, 10 * mm, str(doc.page))
        canvas.restoreState()


class LifecycleGraphic(Flowable):
    def __init__(self, width: float, height: float = 34 * mm) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        labels = ["WorkUnit", "Contract", "Policy", "Plan", "Execute", "Verify", "Evidence"]
        gap = 4.2 * mm
        box_width = (self.width - gap * (len(labels) - 1)) / len(labels)
        box_height = 13 * mm
        y = 9 * mm
        for index, label in enumerate(labels):
            x = index * (box_width + gap)
            fill = FOREST if index in {0, 3, 6} else TEAL
            self.canv.setFillColor(fill)
            self.canv.setStrokeColor(fill)
            self.canv.roundRect(x, y, box_width, box_height, 2.5, fill=1, stroke=1)
            self.canv.setFillColor(PAPER)
            self.canv.setFont(FONT_BOLD, 6.9)
            self.canv.drawCentredString(x + box_width / 2, y + 5.1 * mm, label)
            if index < len(labels) - 1:
                start = x + box_width + 0.6 * mm
                end = x + box_width + gap - 0.6 * mm
                center = y + box_height / 2
                self.canv.setStrokeColor(AMBER)
                self.canv.setFillColor(AMBER)
                self.canv.setLineWidth(1.1)
                self.canv.line(start, center, end, center)
                self.canv.line(end, center, end - 1.4 * mm, center + 1.1 * mm)
                self.canv.line(end, center, end - 1.4 * mm, center - 1.1 * mm)


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "CoverEyebrow": ParagraphStyle(
            "CoverEyebrow",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
            textColor=TEAL,
            spaceAfter=6,
        ),
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=29,
            leading=32,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=15,
            leading=20,
            textColor=FOREST,
            spaceAfter=18,
        ),
        "CoverAuthor": ParagraphStyle(
            "CoverAuthor",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=13,
            textColor=MUTED,
            alignment=TA_LEFT,
            spaceAfter=16,
        ),
        "CoverBody": ParagraphStyle(
            "CoverBody",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=15,
            textColor=INK,
            spaceAfter=12,
        ),
        "Heading2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=17,
            leading=21,
            textColor=FOREST,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "Heading3": ParagraphStyle(
            "Heading3",
            parent=base["Heading3"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=TEAL,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "Heading4": ParagraphStyle(
            "Heading4",
            parent=base["Heading4"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=13.5,
            textColor=INK,
            spaceAfter=6,
            allowWidows=0,
            allowOrphans=0,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=7.6,
            leading=10.2,
            textColor=INK,
        ),
        "SmallBold": ParagraphStyle(
            "SmallBold",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.6,
            leading=10.2,
            textColor=INK,
        ),
        "SmallHeader": ParagraphStyle(
            "SmallHeader",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.6,
            leading=10.2,
            textColor=PAPER,
        ),
        "Reference": ParagraphStyle(
            "Reference",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=7.8,
            leading=10.4,
            textColor=INK,
            spaceAfter=2,
            allowWidows=0,
            allowOrphans=0,
        ),
        "FigureCaption": ParagraphStyle(
            "FigureCaption",
            parent=base["BodyText"],
            fontName=FONT_ITALIC,
            fontSize=7.8,
            leading=10.4,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=8,
        ),
        "Quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10.2,
            leading=15,
            textColor=FOREST,
            leftIndent=12,
            rightIndent=8,
            borderColor=AMBER,
            borderWidth=0,
            borderPadding=(8, 10, 8, 12),
            backColor=SOFT,
            spaceBefore=5,
            spaceAfter=10,
        ),
        "Code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName=FONT_REGULAR,
            fontSize=7.3,
            leading=9.6,
            textColor=DEEP,
            leftIndent=7,
            rightIndent=7,
            borderColor=RULE,
            borderWidth=0.5,
            borderPadding=8,
            backColor=SOFT,
            spaceBefore=4,
            spaceAfter=9,
        ),
        "TOCHeading": ParagraphStyle(
            "TOCHeading",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=FOREST,
            spaceAfter=12,
        ),
        "TOCEntry": ParagraphStyle(
            "TOCEntry",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=14,
            textColor=INK,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=2,
        ),
    }


def cover_story(styles: dict[str, ParagraphStyle], width: float) -> list[Flowable]:
    metric_style = ParagraphStyle(
        "Metric",
        parent=styles["Small"],
        alignment=TA_CENTER,
        textColor=INK,
        fontSize=8,
        leading=11,
    )
    metrics = Table(
        [[
            Paragraph("<b>EXACT BY DEFAULT</b><br/>Unknown data remains byte-identical", metric_style),
            Paragraph("<b>VERIFIER BACKED</b><br/>Candidate output must prove its contract", metric_style),
            Paragraph("<b>OPEN SOFTWARE</b><br/>Apache-2.0 reference implementation", metric_style),
        ]],
        colWidths=[width / 3] * 3,
        rowHeights=[24 * mm],
    )
    metrics.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    metadata = Table(
        [
            [Paragraph("VERSION", styles["SmallBold"]), Paragraph("1.0", styles["Small"])],
            [Paragraph("FIRST PUBLISHED", styles["SmallBold"]), Paragraph("2026-07-11", styles["Small"])],
            [Paragraph("REVISED", styles["SmallBold"]), Paragraph("2026-07-15", styles["Small"])],
            [Paragraph("REPOSITORY", styles["SmallBold"]), Paragraph("github.com/thewisecrab/urp", styles["Small"])],
            [Paragraph("ARTICLE LICENSE", styles["SmallBold"]), Paragraph(ARTICLE_LICENSE, styles["Small"])],
            [Paragraph("SOFTWARE LICENSE", styles["SmallBold"]), Paragraph(SOFTWARE_LICENSE, styles["Small"])],
        ],
        colWidths=[40 * mm, width - 40 * mm],
    )
    metadata.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [
        Spacer(1, 17 * mm),
        Paragraph("OPEN-SOURCE SYSTEMS TECHNICAL REPORT", styles["CoverEyebrow"]),
        Paragraph("Universal Reduction Plane", styles["CoverTitle"]),
        Paragraph("A compatibility-first control plane for reducing data and AI waste", styles["CoverSubtitle"]),
        Paragraph(f"{AUTHOR}<br/>{AFFILIATION}", styles["CoverAuthor"]),
        HRFlowable(width="100%", thickness=2, color=AMBER, spaceBefore=0, spaceAfter=14),
        Paragraph(
            "URP studies whether storage reduction, exact AI caching, context reduction, routing, and future reducers can share one preservation contract, policy decision, verification standard, and audit model.",
            styles["CoverBody"],
        ),
        Spacer(1, 4 * mm),
        metrics,
        Spacer(1, 10 * mm),
        metadata,
        Spacer(1, 8 * mm),
        Paragraph(
            "Evidence note: local measurements prove implementation paths on controlled fixtures. Portfolio impact figures are transparent modeled scenarios, not forecasts or guaranteed savings.",
            styles["Small"],
        ),
        PageBreak(),
    ]


def toc_story(styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCEntry"]]
    toc.tableStyle.add("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR)
    return [
        Paragraph("Contents", styles["TOCHeading"]),
        Paragraph(
            "The report separates measured repository evidence, modeled scenarios, and external context so each claim can be evaluated on its own terms.",
            styles["Body"],
        ),
        Spacer(1, 5 * mm),
        toc,
        PageBreak(),
    ]


def markdown_story(source: str, styles: dict[str, ParagraphStyle], width: float) -> list[Flowable]:
    lines = source.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == "## Abstract"), 0)
    lines = lines[start:]
    story: list[Flowable] = []
    index = 0
    reference_mode = False
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            if language == "mermaid":
                story.extend(
                    [
                        Spacer(1, 2 * mm),
                        LifecycleGraphic(width),
                        Paragraph(
                            "Figure 1. URP's contract-preserving reduction lifecycle. Rejected candidates follow a safe baseline fallback before evidence is recorded.",
                            styles["FigureCaption"],
                        ),
                    ]
                )
            else:
                story.append(XPreformatted(html.escape("\n".join(code)), styles["Code"]))
            continue
        if stripped.startswith("#### "):
            story.append(Paragraph(inline_markup(stripped[5:]), styles["Heading4"]))
            index += 1
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(inline_markup(stripped[4:]), styles["Heading3"]))
            index += 1
            continue
        if stripped.startswith("## "):
            heading = stripped[3:]
            reference_mode = heading.startswith("Appendix B: references")
            story.append(Paragraph(inline_markup(heading), styles["Heading2"]))
            index += 1
            continue
        if stripped.startswith("# "):
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            table_lines = [stripped]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            story.append(build_table(table_lines, styles, width))
            story.append(Spacer(1, 3 * mm))
            continue
        if stripped.startswith(">"):
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip("> "))
                index += 1
            story.append(Paragraph(inline_markup(" ".join(quote)), styles["Quote"]))
            continue
        if re.match(r"^-\s+", stripped):
            items: list[str] = []
            while index < len(lines) and re.match(r"^-\s+", lines[index].strip()):
                items.append(re.sub(r"^-\s+", "", lines[index].strip()))
                index += 1
            story.append(build_list(items, styles, ordered=False))
            story.append(Spacer(1, 2 * mm))
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while index < len(lines) and re.match(r"^\d+\.\s+", lines[index].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[index].strip()))
                index += 1
            story.append(build_list(items, styles, ordered=True, compact=reference_mode))
            story.append(Spacer(1, 2 * mm))
            continue
        paragraph = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines, index):
            paragraph.append(lines[index].strip())
            index += 1
        story.append(Paragraph(inline_markup(" ".join(paragraph)), styles["Body"]))
    return story


def build_table(lines: Sequence[str], styles: dict[str, ParagraphStyle], width: float) -> LongTable:
    rows = [_split_table_row(line) for line in lines]
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    data: list[list[Paragraph]] = []
    for row_index, row in enumerate(normalized):
        style = styles["SmallHeader"] if row_index == 0 else styles["Small"]
        data.append([Paragraph(inline_markup(cell), style) for cell in row])
    if column_count == 2:
        widths = [width * 0.34, width * 0.66]
    elif column_count == 3:
        widths = [width * 0.27, width * 0.28, width * 0.45]
    else:
        widths = [width / column_count] * column_count
    table = LongTable(data, colWidths=widths, repeatRows=1, splitByRow=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
                ("BACKGROUND", (0, 0), (-1, 0), FOREST),
                ("TEXTCOLOR", (0, 0), (-1, 0), PAPER),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SOFT]),
            ]
        )
    )
    return table


def build_list(
    items: Iterable[str],
    styles: dict[str, ParagraphStyle],
    ordered: bool,
    compact: bool = False,
) -> ListFlowable:
    item_style = styles["Reference"] if compact else styles["Body"]
    rows = [ListItem(Paragraph(inline_markup(item), item_style), leftIndent=11) for item in items]
    options = {"start": "1" if ordered else "-"}
    return ListFlowable(
        rows,
        bulletType="1" if ordered else "bullet",
        leftIndent=18,
        bulletFontName=FONT_BOLD,
        bulletFontSize=6.8 if compact else 7.5,
        bulletColor=TEAL,
        spaceBefore=1,
        spaceAfter=2,
        **options,
    )


def inline_markup(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda match: f'<link href="{match.group(2)}" color="#007f8b">{match.group(1)}</link>',
        escaped,
    )
    escaped = re.sub(
        r"`([^`]+)`",
        lambda match: f'<font name="{FONT_REGULAR}" color="#0b241f">{match.group(1)}</font>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    return escaped


def _starts_block(lines: Sequence[str], index: int) -> bool:
    stripped = lines[index].strip()
    return bool(
        stripped.startswith(("#", "```", ">", "|"))
        or re.match(r"^-\s+", stripped)
        or re.match(r"^\d+\.\s+", stripped)
    )


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line.strip())
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    register_fonts()
    styles = build_styles()
    doc = WhitePaperDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=FULL_TITLE,
        author=AUTHOR,
        subject="A compatibility-first control plane for reducing data and AI waste",
        creator="URP publication renderer",
        keywords="URP, data reduction, AI infrastructure, exact cache, FinOps, S3 gateway",
        invariant=1,
        pageCompression=1,
        lang="en-US",
        initialFontName=FONT_REGULAR,
        initialFontSize=10,
        initialLeading=12,
    )
    story = cover_story(styles, doc.width)
    story.extend(toc_story(styles))
    story.extend(markdown_story(source.read_text(encoding="utf-8"), styles, doc.width))
    doc.multiBuild(story)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the URP Markdown technical paper as a publication PDF")
    parser.add_argument("--source", default="docs/WHITE_PAPER.md")
    parser.add_argument("--output", default="output/pdf/URP-White-Paper-v1.0.pdf")
    parser.add_argument("--public-copy", default="docs/assets/URP-White-Paper-v1.0.pdf")
    args = parser.parse_args()
    output = Path(args.output)
    render(Path(args.source), output)
    if args.public_copy:
        public_copy = Path(args.public_copy)
        public_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, public_copy)
    print(args.output)


if __name__ == "__main__":
    main()
