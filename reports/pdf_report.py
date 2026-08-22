"""PDF export helpers for executive reconciliation audits."""

from __future__ import annotations

from io import BytesIO
from typing import Mapping, Optional, Union

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _summary_rows(summary: Optional[pd.DataFrame]) -> list[list[str]]:
    if summary is None or summary.empty or not {"Metric", "Value"}.issubset(summary.columns):
        return [["Metric", "Value"], ["No summary metrics available", "-"]]

    rows = [["Metric", "Value"]]
    for _, row in summary.iterrows():
        value = row["Value"]
        if isinstance(value, float):
            value = f"{value:,.2f}"
        rows.append([str(row["Metric"]), str(value)])
    return rows


def _high_risk_rows(risk_scores: Optional[pd.DataFrame]) -> list[list[str]]:
    columns = ["GSTIN", "Vendor Name", "Risk Score", "Risk Category", "Blocked ITC (Rs)"]
    if risk_scores is None or risk_scores.empty:
        return [columns, ["-", "No high-risk vendors identified", "-", "-", "-"]]

    category_column = "Risk Category" if "Risk Category" in risk_scores else "risk_level"
    high_risk = risk_scores[
        risk_scores[category_column].astype(str).str.lower() == "high"
    ].copy()
    if high_risk.empty:
        return [columns, ["-", "No high-risk vendors identified", "-", "-", "-"]]

    rows = [columns]
    for _, row in high_risk.sort_values("risk_score", ascending=False).iterrows():
        rows.append(
            [
                str(row.get("GSTIN", "")),
                str(row.get("Vendor Name", "Unknown Vendor")),
                f"{float(row.get('risk_score', 0)):,.2f}",
                str(row.get(category_column, "High")),
                f"{float(row.get('blocked_itc', 0)):,.2f}",
            ]
        )
    return rows


def _table_style(header_background: str = "#1F4E78") -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_background)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C7D1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def generate_pdf_report(
    summary: Optional[pd.DataFrame] = None,
    risk_scores: Optional[pd.DataFrame] = None,
    output: Optional[Union[str, BytesIO]] = None,
) -> BytesIO:
    """Generate an executive reconciliation audit PDF and return its buffer."""
    buffer = output if isinstance(output, BytesIO) else BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Executive Risk & Reconciliation Audit",
        author="ITC Reconciliation Engine",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E78"),
        fontSize=20,
        spaceAfter=6 * mm,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1F4E78"),
        spaceBefore=4 * mm,
        spaceAfter=3 * mm,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
    )

    summary_data = _summary_rows(summary)
    risk_data = _high_risk_rows(risk_scores)
    story = [
        Paragraph("Executive Risk &amp; Reconciliation Audit", title_style),
        Paragraph(
            "A consolidated review of reconciliation outcomes, blocked input tax credit, and vendor risk exposure.",
            body_style,
        ),
        Spacer(1, 4 * mm),
        Paragraph("Summary Metrics", section_style),
    ]

    summary_table = Table(summary_data, colWidths=[115 * mm, 55 * mm], repeatRows=1)
    summary_table.setStyle(_table_style())
    summary_table.setStyle(
        TableStyle([("ALIGN", (1, 1), (1, -1), "RIGHT")])
    )
    story.extend([summary_table, Paragraph("High-Risk Vendors", section_style)])

    risk_table = Table(
        risk_data,
        colWidths=[31 * mm, 55 * mm, 25 * mm, 30 * mm, 30 * mm],
        repeatRows=1,
    )
    risk_table.setStyle(_table_style("#8E2F2F"))
    risk_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
            ]
        )
    )
    story.append(risk_table)
    document.build(story)

    buffer.seek(0)
    if isinstance(output, str):
        with open(output, "wb") as file:
            file.write(buffer.getvalue())
        buffer.seek(0)
    return buffer


if __name__ == "__main__":
    generate_pdf_report()
    print("PDF report buffer generated.")
