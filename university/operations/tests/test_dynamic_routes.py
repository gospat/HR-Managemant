from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.http import JsonResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.views import View
from employee.models import Employee, EmployeeWorkInformation
from core.testkit import make_company, make_employee, make_user
from university.operations.dynamic_routes import PREFIX, register


class SyntheticBulkView(View):
    model = Employee

    def serve_bulk_form(self, request):
        return JsonResponse(
            {
                "actor": request.user.pk,
                "path": request.path,
                "instance": id(self),
                "view_id": self.view_id,
            }
        )

    def handle_bulk_submission(self, request):
        return JsonResponse({"post_bulk_path": self.post_bulk_path})


class SyntheticPopupView(View):
    model = Employee

    def get(self, request):
        return JsonResponse({"actor": request.user.pk})


class DynamicCallbackSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Callback University")
        cls.other = make_company("Other institution")
        cls.root = make_user("callback-root", is_superuser=True)
        make_employee(company=cls.company, user=cls.root, email="root@callback.test")
        cls.user = make_user("callback-officer")
        cls.employee = make_employee(
            company=cls.company, user=cls.user, email="officer@callback.test"
        )
        cls.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="employee", codename="change_employee"
            )
        )

    def registered(self, client, user, method="serve_bulk_form"):
        client.force_login(user, backend="base.auth_backends.CompanyScopedBackend")
        request = RequestFactory().get("/original-module/")
        request.user = user
        request.session = client.session
        owner = SyntheticBulkView()
        owner.setup(request)
        owner.view_id = "synthetic-list"
        view = getattr(owner, method) if method else SyntheticPopupView.as_view()
        with patch(
            "core.horilla_middlewares._thread_locals",
            SimpleNamespace(request=request),
        ):
            url = "/" + register("synthetic-" + request.session.session_key, view)
        self.assertNotIn(request.session.session_key, url)
        return url, owner

    def test_bound_callback_is_reconstructed_with_current_request(self):
        client = Client()
        url, original = self.registered(client, self.root)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actor"], self.root.pk)
        self.assertEqual(response.json()["path"], url)
        self.assertNotEqual(response.json()["instance"], id(original))
        self.assertEqual(response.json()["view_id"], "synthetic-list")
        self.assertIn("no-store", response["Cache-Control"])

    def test_another_login_even_for_the_same_user_cannot_replay_the_url(self):
        first = Client()
        url, _ = self.registered(first, self.root)
        other = Client()
        other.force_login(self.root, backend="base.auth_backends.CompanyScopedBackend")
        self.assertEqual(other.get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 403)

    def test_revoked_permissions_and_changed_institution_are_checked_again(self):
        client = Client()
        url, _ = self.registered(client, self.user)
        self.assertEqual(client.get(url).status_code, 200)
        self.user.user_permissions.clear()
        self.assertEqual(client.get(url).status_code, 403)
        EmployeeWorkInformation.objects.filter(employee_id=self.employee).update(
            company_id=self.other
        )
        self.assertEqual(client.get(url).status_code, 404)

    def test_expired_callback_fails_closed(self):
        client = Client()
        url, _ = self.registered(client, self.root)
        token = url.strip("/").split("/")[-1]
        cache.delete(PREFIX + token)
        self.assertEqual(client.get(url).status_code, 404)

    def test_csrf_protects_post_and_bulk_retry_uses_the_opaque_url(self):
        client = Client(enforce_csrf_checks=True)
        url, _ = self.registered(client, self.root, method="handle_bulk_submission")
        self.assertEqual(client.post(url).status_code, 403)
        csrf = client.get("/university-api/session/").json()["csrf"]
        response = client.post(url, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual("/" + response.json()["post_bulk_path"], url)

    def test_popup_dispatch_keeps_view_authorization(self):
        client = Client()
        url, _ = self.registered(client, self.root, method=None)
        self.assertEqual(client.get(url).json()["actor"], self.root.pk)

    def test_unassigned_officer_cannot_register_a_callback(self):
        from django.core.exceptions import PermissionDenied

        orphan = make_user("callback-unassigned")
        with self.assertRaises(PermissionDenied):
            self.registered(Client(), orphan)

    @override_settings(ROOT_URLCONF="university.operations.urls")
    def test_production_root_uses_the_shared_dispatcher_too(self):
        from hr_views.generic.cbv.views import register_dynamic_url

        client = Client()
        client.force_login(self.root, backend="base.auth_backends.CompanyScopedBackend")
        request = RequestFactory().get("/production-module/")
        request.user = self.root
        request.session = client.session
        with patch(
            "core.horilla_middlewares._thread_locals",
            SimpleNamespace(request=request),
        ):
            url = register_dynamic_url(
                "production-probe-" + request.session.session_key,
                SyntheticPopupView.as_view(),
            )
        self.assertTrue(url.startswith("university-dynamic/"))
        self.assertNotIn(request.session.session_key, url)
        self.assertEqual(client.get("/" + url).status_code, 200)
