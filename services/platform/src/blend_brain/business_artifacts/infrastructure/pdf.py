"""Professional draft-watermarked PDF rendering with ReportLab."""

from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
)

from blend_brain.business_artifacts.domain import (
    ArtifactExportError,
    BusinessArtifact,
    ProjectOnePagerArtifact,
)

_NAVY = colors.HexColor("#102A43")
_BLUE = colors.HexColor("#1367D1")
_MUTED = colors.HexColor("#52677D")
_LIGHT = colors.HexColor("#E8EEF5")


class ReportLabPdfRenderer:
    """Render text-first PDFs without executing artifact markup."""

    def render(self, artifact: BusinessArtifact) -> bytes:
        """Render an artifact and enforce the one-page template contract."""
        buffer = BytesIO()
        document = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=22 * mm,
            bottomMargin=18 * mm,
            title=artifact.title,
            author="Blend Knowledge Brain",
            subject="AI-generated draft business artifact",
        )
        frame = Frame(
            document.leftMargin,
            document.bottomMargin,
            document.width,
            document.height,
            id="content",
        )
        document.addPageTemplates(
            [PageTemplate(id="artifact", frames=frame, onPage=self._decorate_page)]
        )
        story = self._story(artifact)
        try:
            document.build(story)
        except Exception as exception:
            raise ArtifactExportError("ReportLab could not render the artifact") from exception
        if isinstance(artifact, ProjectOnePagerArtifact) and document.page > 1:
            raise ArtifactExportError(
                "Project one-pager content exceeds the single-page export limit",
                page_count=document.page,
            )
        return buffer.getvalue()

    @staticmethod
    def _story(artifact: BusinessArtifact) -> list[Flowable]:
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "ArtifactTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=_NAVY,
            alignment=TA_LEFT,
            spaceAfter=4 * mm,
        )
        subtitle = ParagraphStyle(
            "ArtifactSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=_MUTED,
            spaceAfter=5 * mm,
        )
        heading = ParagraphStyle(
            "ArtifactHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=_BLUE,
            spaceBefore=2.5 * mm,
            spaceAfter=1.5 * mm,
        )
        body = ParagraphStyle(
            "ArtifactBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=_NAVY,
            leftIndent=4 * mm,
            firstLineIndent=-3 * mm,
            spaceAfter=1.5 * mm,
        )
        empty = ParagraphStyle(
            "ArtifactEmpty",
            parent=body,
            textColor=_MUTED,
            leftIndent=0,
            firstLineIndent=0,
        )
        story: list[Flowable] = [Paragraph(escape(artifact.title), title)]
        if isinstance(artifact, ProjectOnePagerArtifact):
            generated = artifact.created_at.strftime("Generated %Y-%m-%d - Sales Brief")
            story.append(Paragraph(escape(generated), subtitle))
        if artifact.subtitle:
            story.append(Paragraph(escape(artifact.subtitle), subtitle))
        story.append(Paragraph("DRAFT • AI-GENERATED • REQUIRES HUMAN REVIEW", subtitle))
        for section in artifact.sections:
            story.append(Paragraph(escape(section.heading), heading))
            if not section.statements:
                story.append(Paragraph("Not documented in the supplied evidence.", empty))
                continue
            for statement in section.statements:
                references = " ".join(
                    f"[{escape(citation.source_id)}]" for citation in statement.citations
                )
                story.append(
                    Paragraph(
                        f"• {escape(statement.text)} <font color='#52677D'>{references}</font>",
                        body,
                    )
                )
        citations = {
            citation.source_id: citation
            for section in artifact.sections
            for statement in section.statements
            for citation in statement.citations
        }
        if citations and not isinstance(artifact, ProjectOnePagerArtifact):
            story.append(Paragraph("Source Notes", heading))
            for source_id, citation in sorted(citations.items()):
                locator = citation.filename or "Supplied brief/source"
                if citation.section_sequence is not None:
                    locator = f"{locator}, section {citation.section_sequence}"
                story.append(
                    Paragraph(
                        f"[{escape(source_id)}] {escape(locator)} — “{escape(citation.quote)}”",
                        empty,
                    )
                )
        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                f"Artifact ID: {escape(artifact.artifact_id)} • Content: "
                f"{escape(artifact.content_sha256[:12])}",
                empty,
            )
        )
        return story

    @staticmethod
    def _decorate_page(canvas: Any, document: Any) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(_NAVY)
        canvas.rect(0, height - 12 * mm, width, 12 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(18 * mm, height - 7.5 * mm, "BLEND KNOWLEDGE BRAIN")
        canvas.setFillColor(_LIGHT)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - 18 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()
