from datetime import date
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from core.testkit import make_company, make_employee
from core.testkit.factories import make_payslip
from hr_api.api_views.payroll.views import PayslipPDFAPIView
from payroll.models.tax_models import PayrollSettings


class PayslipExportAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Payslip University")
        cls.other_company = make_company("Other institution")
        cls.owner = make_employee(company=cls.company, email="owner@payslip.test")
        cls.peer = make_employee(company=cls.company, email="peer@payslip.test")
        cls.outsider = make_employee(
            company=cls.other_company, email="outsider@payslip.test"
        )
        cls.payslip = make_payslip(
            employee=cls.owner, start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )
        cls.payslip.pay_head_data = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "allowances": [],
            "net_pay": 4000,
            "basic_pay": 5000,
            "gross_pay": 5000,
        }
        cls.payslip.save(update_fields=["pay_head_data"])
        PayrollSettings.objects.create(company_id=cls.company, currency_symbol="₦")

    def request(self, user, format="pdf"):
        request = APIRequestFactory().get("/api/payslip/", {"format": format})
        force_authenticate(request, user=user)
        return PayslipPDFAPIView.as_view()(request, id=self.payslip.pk)

    def test_owner_receives_pdf_through_real_content_negotiation(self):
        response = self.request(self.owner.employee_user_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("no-store", response["Cache-Control"])
        import io
        from pypdf import PdfReader

        text = "".join(
            page.extract_text()
            for page in PdfReader(io.BytesIO(response.content)).pages
        )
        self.assertIn("₦", text)
        self.assertIn("4000.00", text)
        self.assertNotIn("₹", text)

    def test_peer_and_cross_institution_hr_cannot_export(self):
        self.assertEqual(self.request(self.peer.employee_user_id).status_code, 403)
        user = self.outsider.employee_user_id
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="payroll", codename="view_payslip"
            )
        )
        self.assertEqual(self.request(user).status_code, 404)

    def test_invalid_dates_and_unconfigured_currency_are_actionable(self):
        self.payslip.pay_head_data["start_date"] = "not-a-date"
        self.payslip.save(update_fields=["pay_head_data"])
        self.assertEqual(self.request(self.owner.employee_user_id).status_code, 400)
        self.payslip.pay_head_data["start_date"] = "2026-01-01"
        self.payslip.save(update_fields=["pay_head_data"])
        PayrollSettings.objects.entire().filter(company_id=self.company).delete()
        self.assertEqual(self.request(self.owner.employee_user_id).status_code, 400)

    def test_legacy_download_uses_same_currency_and_scope(self):
        from payroll.views.views import payslip_pdf
        from django.http import Http404

        request = APIRequestFactory().get("/payroll/payslip-pdf/")
        from django.contrib.sessions.middleware import SessionMiddleware

        SessionMiddleware(lambda request: None).process_request(request)
        request.user = self.owner.employee_user_id
        response = payslip_pdf(request, self.payslip.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF-"))
        outsider = self.outsider.employee_user_id
        outsider.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="payroll", codename="view_payslip"
            )
        )
        request.user = outsider
        with self.assertRaises(Http404):
            payslip_pdf(request, self.payslip.pk)

    def test_api_administrator_does_not_need_an_employee_profile(self):
        from core.testkit import make_user

        user = make_user("export-admin", is_superuser=True)
        self.assertEqual(self.request(user).status_code, 200)
