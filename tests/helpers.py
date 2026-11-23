"""Test documents generated on the fly (never the owner's real CV)."""

from __future__ import annotations

import io
import json

CV_LINES = [
    "Ana Test Example",
    "Backend developer, Python",
    "Experience: Acme Data, backend developer 2021-2024",
    "Built billing APIs with Flask and PostgreSQL.",
    "Skills: Python, SQL, Docker",
]


def make_pdf(lines: list[str] | None = None) -> bytes:
    """A tiny valid one-page PDF with real text (Helvetica)."""
    lines = CV_LINES if lines is None else lines
    ops = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({safe}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objects) + 1, xref))
    return out.getvalue()


def make_docx(lines: list[str] | None = None) -> bytes:
    from docx import Document

    doc = Document()
    for line in CV_LINES if lines is None else lines:
        doc.add_paragraph(line)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


PROFILE = {
    "basics": {"name": "Ana Test Example", "headline": "Backend developer", "email": "",
               "phone": "", "location": "", "links": [], "summary": ""},
    "experience": [{"role": "Backend developer", "company": "Acme Data", "start": "2021",
                    "end": "2024", "location": "", "highlights": ["Built billing APIs"]}],
    "projects": [],
    "education": [],
    "languages": [{"language": "English", "level": "C1"}],
    "skills": ["Python", "SQL"],
}


def profile_json(**changes) -> str:
    data = json.loads(json.dumps(PROFILE))
    data.update(changes)
    return json.dumps(data)
