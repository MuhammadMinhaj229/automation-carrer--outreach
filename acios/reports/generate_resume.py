"""
Generate a PDF resume only from a private, locally configured candidate profile.
No real candidate identity or employment history is embedded in source control.
"""
from pathlib import Path
import html
import yaml
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROFILE_PATH = BASE_DIR / "config" / "candidate_profile.yaml"

def generate_resume_pdf(output_path: Path):
    if not PROFILE_PATH.exists():
        raise ValueError("Configure the private candidate profile before generating a resume.")
    try:
        data = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("The private candidate profile could not be read.") from exc
    candidate = data.get("candidate") or {}
    name = str(candidate.get("full_name") or "").strip()
    if not name:
        raise ValueError("A candidate name is required in the private profile before generating a resume.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=42, leftMargin=42, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("CandidateName", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=5)
    section_style = ParagraphStyle("SectionHeading", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("ResumeBody", parent=styles["BodyText"], fontSize=9, leading=12, spaceAfter=4)
    contact = " | ".join(str(candidate.get(k) or "").strip() for k in ("email", "phone") if str(candidate.get(k) or "").strip())
    links = " | ".join(str(candidate.get(k) or "").strip() for k in ("linkedin_url", "portfolio_url") if str(candidate.get(k) or "").strip())
    elements = [Paragraph(html.escape(name), name_style)]
    if contact: elements.append(Paragraph(html.escape(contact), body_style))
    if links: elements.append(Paragraph(html.escape(links), body_style))
    degree = str(candidate.get("academic_background") or "").strip()
    if degree:
        elements.extend([Spacer(1, 5), Paragraph("EDUCATION", section_style), Paragraph(html.escape(degree), body_style)])
    experiences = data.get("experiences") or {}
    if experiences:
        elements.extend([Spacer(1, 4), HRFlowable(width="100%", thickness=0.5), Paragraph("EXPERIENCE", section_style)])
        for item in experiences.values():
            if not isinstance(item, dict): continue
            org = str(item.get("organization") or "").strip()
            role = str(item.get("role") or "").strip()
            summary = str(item.get("summary") or item.get("focus") or "").strip()
            if not (org or role or summary): continue
            heading = " — ".join(part for part in (org, role) if part)
            if heading: elements.append(Paragraph(html.escape(heading), styles["Heading3"]))
            if summary: elements.append(Paragraph(html.escape(summary), body_style))
    skills = candidate.get("skills") or []
    if skills:
        elements.extend([Paragraph("SKILLS", section_style), Paragraph(html.escape(", ".join(map(str, skills))), body_style)])
    doc.build(elements)
    return output_path

if __name__ == "__main__":
    generate_resume_pdf(BASE_DIR / "data" / "resume" / "master_resume.pdf")
