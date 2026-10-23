"""Document exports without browser execution, URL fetching or local HTML assets."""

import os
from pathlib import Path
import subprocess
import sys

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024


class DocumentRenderError(ValueError):
    pass


def render_pdf(html):
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise DocumentRenderError("Document is missing or exceeds the export limit.")
    root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            [sys.executable, "-m", "university.documents.worker"],
            input=html.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            cwd="/tmp",
            env={"PYTHONPATH": str(root), "LANG": "C.UTF-8"},
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise DocumentRenderError("Document could not be exported safely.") from exc
    pdf = result.stdout
    if not pdf.startswith(b"%PDF-") or len(pdf) > MAX_PDF_BYTES:
        raise DocumentRenderError("Document could not be exported safely.")
    return pdf
