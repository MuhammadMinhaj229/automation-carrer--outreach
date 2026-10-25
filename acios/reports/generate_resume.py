"""
Generates a clean, professional single-page PDF resume for Mohammed Minhaj Mahmood.
Used as the default attachment for Gmail Draft staging and direct dispatch.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_resume_pdf(output_path: Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Styles
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'ContactStyle',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0369a1'),
        fontName='Helvetica-Bold',
        spaceBefore=8,
        spaceAfter=4
    )

    job_title = ParagraphStyle(
        'JobTitle',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold'
    )

    job_sub = ParagraphStyle(
        'JobSub',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748b'),
        fontName='Helvetica-Oblique',
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=4
    )

    elements = []

    # Header
    elements.append(Paragraph("MOHAMMED MINHAJ MAHMOOD", name_style))
    contact_text = (
        "<b>Email:</b> minhajmuhammad229@gmail.com &nbsp;|&nbsp; "
        "<b>Phone:</b> +91 80509 09536 &nbsp;|&nbsp; "
        "<b>LinkedIn:</b> linkedin.com/in/mohammed-minhaj-mahmood-76037b310/"
    )
    elements.append(Paragraph(contact_text, contact_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceBefore=0, spaceAfter=8))

    # Professional Summary
    elements.append(Paragraph("PROFESSIONAL SUMMARY", section_heading))
    summary_text = (
        "Data Systems & Automation Specialist with a strong background in automated data validation pipelines, "
        "enterprise software testing, and reliable ETL workflow development. Proven track record in building Python-based "
        "inspection and data validation scripts for health and agricultural research initiatives (Public Health Foundation of India), "
        "as well as structured feature QA for enterprise AI platforms (Ejada Labs). Focused on ensuring data fidelity, regression stability, "
        "and operational automation across expanding industrial and technical ecosystems in the GCC."
    )
    elements.append(Paragraph(summary_text, bullet_style))

    # Core Competencies
    elements.append(Paragraph("CORE COMPETENCIES & TECHNICAL SKILLS", section_heading))
    skills_text = (
        "<b>Languages & Tools:</b> Python (pandas, NumPy, openpyxl, feedparser, requests), SQL (PostgreSQL, SQLite), Git, Bash<br/>"
        "<b>Data Engineering & Automation:</b> ETL Pipeline Design, Data Quality Auditing, Validation Frameworks, Prefect Orchestration<br/>"
        "<b>Quality Assurance:</b> Regression Testing, Edge-case Simulation, Schema Ingestion Validation, Test Scenario Design<br/>"
        "<b>Domains:</b> AgriTech & Biofuels Data, Enterprise AI Platforms, Public Health & Environmental Research, Operational Reporting"
    )
    elements.append(Paragraph(skills_text, bullet_style))

    # Experience
    elements.append(Paragraph("PROFESSIONAL EXPERIENCE", section_heading))

    # 1. PHFI
    elements.append(Paragraph("Public Health Foundation of India (PHFI) &nbsp;—&nbsp; Research Data Analyst & Automation Assistant", job_title))
    elements.append(Paragraph("Data Validation & Pipeline Engineering", job_sub))
    elements.append(Paragraph("• Architected automated Python validation scripts to detect missing variables, format anomalies, and structural inconsistencies across remote field research and environmental health reports.", bullet_style))
    elements.append(Paragraph("• Ensured zero bad-record propagation into analytical datastores, standardizing multi-source sensor and survey datasets.", bullet_style))

    # 2. Ejada Labs
    elements.append(Paragraph("Ejada Labs &nbsp;—&nbsp; Software QA & Feature Tester", job_title))
    elements.append(Paragraph("Enterprise AI & Platform QA (Sanad AI)", job_sub))
    elements.append(Paragraph("• Conducted rigorous feature testing, structured QA, and end-to-end regression testing on the Sanad AI platform to guarantee model stability.", bullet_style))
    elements.append(Paragraph("• Authored detailed edge-case test suites validating data ingestion pipelines, preventing data drift and interface regressions.", bullet_style))

    # 3. Independent Engagements
    elements.append(Paragraph("Independent Client Engagements &nbsp;—&nbsp; Data Workflow Specialist", job_title))
    elements.append(Paragraph("Operational Automation & Custom ETL", job_sub))
    elements.append(Paragraph("• Engineered automated data cleaning scripts and scheduled ETL workflows for enterprise clients, eliminating manual spreadsheet bottlenecks.", bullet_style))
    elements.append(Paragraph("• Built robust schema-mapping tools transforming unstructured partner outputs into clean operational reports.", bullet_style))

    # Education
    elements.append(Paragraph("EDUCATION", section_heading))
    elements.append(Paragraph("<b>Bachelor of Engineering / Computer Science & Data Science</b>", job_title))
    elements.append(Paragraph("Specialization in Software Systems, Algorithms, and Data Management", job_sub))

    doc.build(elements)
    print(f"Resume generated at: {output_path}")

if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent.parent / "data" / "resume" / "Mohammed_Minhaj_Mahmood_CV.pdf"
    generate_resume_pdf(out_file)
