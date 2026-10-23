import io
from unittest.mock import patch
import subprocess
from django.test import SimpleTestCase
from pypdf import PdfReader
from university.documents import render_pdf, DocumentRenderError


class SafeExportTests(SimpleTestCase):
    def test_payslip_values_unicode_and_table_survive_export(self):
        pdf = render_pdf(
            "<h1>Bells University</h1><p>Salary ₦150,000</p><table><tr><td>Net pay</td><td>125000.50</td></tr></table>"
        )
        reader = PdfReader(io.BytesIO(pdf))
        text = "".join(page.extract_text() for page in reader.pages)
        for value in ("Bells University", "₦150,000", "Net pay", "125000.50"):
            self.assertIn(value, text)

    def test_active_markup_and_resources_are_never_rendered(self):
        pdf = render_pdf(
            '<h1>Approved text</h1><script>SECRET_SCRIPT</script><style>SECRET_STYLE</style><iframe src="file:///etc/passwd">SECRET_FRAME</iframe><img src="http://127.0.0.1:1/private"><img src="file:///etc/passwd"><p>&lt;img src="file:///etc/shadow"&gt;</p>'
        )
        text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("Approved text", text)
        for marker in ("SECRET_SCRIPT", "SECRET_STYLE", "SECRET_FRAME", "root:"):
            self.assertNotIn(marker, text)

    def test_long_tables_span_multiple_pages(self):
        rows = "".join(
            f"<tr><td>Component {i}</td><td>{i}.50</td></tr>" for i in range(150)
        )
        reader = PdfReader(io.BytesIO(render_pdf("<table>" + rows + "</table>")))
        self.assertGreater(len(reader.pages), 1)
        self.assertIn(
            "Component 149", "".join(page.extract_text() for page in reader.pages)
        )

    def test_size_empty_and_runtime_limits_fail_closed(self):
        for html in ("", "x" * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(DocumentRenderError):
                render_pdf(html)
        with patch(
            "university.documents.subprocess.run",
            side_effect=subprocess.TimeoutExpired("worker", 20),
        ):
            with self.assertRaises(DocumentRenderError):
                render_pdf("<p>Document</p>")

    def test_endpoint_returns_private_pdf_without_internal_error_details(self):
        from base.methods import template_pdf

        response = template_pdf("<p>Private salary</p>", filename="payslip.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        with patch(
            "university.documents.render_pdf",
            side_effect=DocumentRenderError("/run/secrets/private-key"),
        ):
            response = template_pdf("<p>Invalid</p>")
        self.assertNotIn(b"/run/secrets", response.content)
