from django.test import TestCase, override_settings
from django.contrib.auth.models import Permission
from horilla.testkit import make_company, make_employee, make_user
from horilla_documents.models import Document
from university.documents.access import can_read_media


class DocumentAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Document University")
        cls.other_company = make_company("Other University")
        cls.owner = make_employee(company=cls.company, email="owner@documents.test")
        cls.peer = make_employee(company=cls.company, email="peer@documents.test")
        cls.outsider = make_employee(
            company=cls.other_company, email="other@documents.test"
        )
        cls.hr = make_employee(company=cls.company, email="hr@documents.test")
        cls.hr.employee_user_id.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="horilla_documents", codename="view_document"
            )
        )
        cls.path = "horilla_documents/document/confidential.pdf"
        cls.document = Document.objects.create(
            title="Private document", employee_id=cls.owner, document=cls.path
        )

    def test_owner_and_scoped_hr_can_read(self):
        self.assertTrue(can_read_media(self.owner.employee_user_id, self.path))
        self.assertTrue(can_read_media(self.hr.employee_user_id, self.path))

    def test_peer_and_cross_company_hr_are_denied(self):
        self.assertFalse(can_read_media(self.peer.employee_user_id, self.path))
        user = self.outsider.employee_user_id
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="horilla_documents", codename="view_document"
            )
        )
        self.assertFalse(can_read_media(user, self.path))

    def test_unknown_paths_traversal_and_inactive_login_are_denied(self):
        for path in (
            "other/private.pdf",
            "base/icon/../../private.pdf",
            "/private.pdf",
            "file%2fpdf",
            "private\\file",
        ):
            self.assertFalse(can_read_media(self.owner.employee_user_id, path))
        user = self.owner.employee_user_id
        user.is_active = False
        self.assertFalse(can_read_media(user, self.path))

    def test_removing_document_registration_revokes_access(self):
        Document.objects.entire().filter(pk=self.document.pk).update(document="")
        self.assertFalse(can_read_media(self.owner.employee_user_id, self.path))

    def test_download_boundary_enforces_ownership_and_private_cache_headers(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from university.operations.middleware import ProductionBoundaryMiddleware

        middleware = ProductionBoundaryMiddleware(
            lambda request: HttpResponse("private")
        )
        for employee, expected in ((self.owner, 200), (self.peer, 403)):
            request = RequestFactory().get("/media/" + self.path)
            request.user = employee.employee_user_id
            response = middleware(request)
            self.assertEqual(response.status_code, expected)
            self.assertIn("no-store", response["Cache-Control"])
