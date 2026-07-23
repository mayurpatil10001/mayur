"""
scripts/convert_md_to_pdf.py
============================
Converts DETAILED_SESSION_PNL_AB_AUDIT.md into a beautifully styled PDF:
`DETAILED_SESSION_PNL_AB_AUDIT.pdf`
"""

import os
import sys
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

PROJECT_ROOT = Path(__file__).parent.parent
MD_FILE = PROJECT_ROOT / "DETAILED_SESSION_PNL_AB_AUDIT.md"
PDF_FILE = PROJECT_ROOT / "DETAILED_SESSION_PNL_AB_AUDIT.pdf"


def format_markdown_text(text: str) -> str:
    """Format markdown bold, code, and escape XML special characters."""
    # Escape XML characters first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Restore bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Restore inline code tags
    text = re.sub(r'`([^`]+)`', r'<font face="Courier" color="#1e293b">\1</font>', text)
    
    return text


def build_pdf():
    print(f"Reading {MD_FILE}...")
    with open(MD_FILE, "r", encoding="utf-8") as f:
        md_text = f.read()

    doc = SimpleDocTemplate(
        str(PDF_FILE),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#1e293b")  # Dark slate
    ACCENT = colors.HexColor("#2563eb")   # Royal blue
    TEXT_DARK = colors.HexColor("#0f172a")
    BG_ALT = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#cbd5e1")

    # Define Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        spaceAfter=10
    )

    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=ACCENT,
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=TEXT_DARK,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=body_style,
        leftIndent=12,
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['BodyText'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=TEXT_DARK,
        alignment=0
    )

    story = []
    lines = md_text.split('\n')
    in_table = False
    table_lines = []

    def flush_table(t_lines):
        if not t_lines: return None
        parsed_rows = []
        for line in t_lines:
            if re.match(r'^\s*\|?\s*:?-+:?\s*\|', line):
                continue  # Skip header separator row
            cells = [c.strip() for c in line.strip('|').split('|')]
            parsed_rows.append(cells)

        if not parsed_rows: return None

        # Build ReportLab Table
        table_data = []
        # Header
        header = [Paragraph(f"<b>{format_markdown_text(c)}</b>", table_header_style) for c in parsed_rows[0]]
        table_data.append(header)

        # Rows
        for row in parsed_rows[1:]:
            r_cells = []
            for cell in row:
                r_cells.append(Paragraph(format_markdown_text(cell), table_cell_style))
            table_data.append(r_cells)

        num_cols = len(parsed_rows[0])
        col_width = (7.5 * inch) / num_cols

        t = Table(table_data, colWidths=[col_width] * num_cols)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_ALT]),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ]))
        return t

    for line in lines:
        stripped = line.strip()

        # Table detection
        if stripped.startswith('|'):
            in_table = True
            table_lines.append(stripped)
            continue
        elif in_table:
            in_table = False
            t_obj = flush_table(table_lines)
            if t_obj:
                story.append(t_obj)
                story.append(Spacer(1, 8))
            table_lines = []

        if not stripped:
            continue

        if stripped.startswith('# '):
            text = format_markdown_text(stripped[2:].strip())
            story.append(Paragraph(text, title_style))
            story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceAfter=8))
        elif stripped.startswith('## '):
            text = format_markdown_text(stripped[3:].strip())
            story.append(Paragraph(text, h2_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceAfter=6))
        elif stripped.startswith('### '):
            text = format_markdown_text(stripped[4:].strip())
            story.append(Paragraph(f"<b>{text}</b>", body_style))
            story.append(Spacer(1, 4))
        elif stripped.startswith('- ') or stripped.startswith('* '):
            text = format_markdown_text(stripped[2:].strip())
            story.append(Paragraph(f"• {text}", bullet_style))
        elif stripped.startswith('---'):
            story.append(Spacer(1, 6))
        else:
            text = format_markdown_text(stripped)
            story.append(Paragraph(text, body_style))
            story.append(Spacer(1, 4))

    # Catch trailing table
    if in_table:
        t_obj = flush_table(table_lines)
        if t_obj:
            story.append(t_obj)

    print(f"Building PDF document {PDF_FILE}...")
    doc.build(story)
    print(f"Successfully generated PDF: {PDF_FILE}")


if __name__ == "__main__":
    build_pdf()
