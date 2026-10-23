"""Real Chromium journey against Next.js and Django with the isolated test DB.

Requires installed frontend dependencies and system Chromium (or CHROMIUM_PATH).
Run separately from the API suite because LiveServerTestCase flushes its DB.
"""

from datetime import date
from copy import deepcopy
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

from django.conf import settings
from django.test import LiveServerTestCase, override_settings
from playwright.sync_api import sync_playwright, expect

from horilla.testkit import make_company, make_employee, make_user
from employee.models import Employee
from university.people.models import StaffChange, StaffProfile
from university.governance.models import UniversityPolicy, PromotionRequest
from university.governance.defaults import DEFAULTS, POLICY_VERSION
from university.governance.services import adopt_policy


@override_settings(CSRF_TRUSTED_ORIGINS=["http://127.0.0.1:3100"])
class PortalBrowserTests(LiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frontend = Path(settings.BASE_DIR) / "frontend"
        cls.log = open("/tmp/university-browser-frontend.log", "w")
        cls.frontend = subprocess.Popen(
            [
                "node",
                "node_modules/next/dist/bin/next",
                "dev",
                "-H",
                "127.0.0.1",
                "-p",
                "3100",
            ],
            cwd=frontend,
            env={**os.environ, "HR_BACKEND_URL": cls.live_server_url},
            stdout=cls.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        cls.addClassCleanup(cls.stop_frontend)
        for _ in range(100):
            if cls.frontend.poll() is not None:
                raise RuntimeError(
                    "Browser-test frontend exited; see /tmp/university-browser-frontend.log"
                )
            try:
                if (
                    urllib.request.urlopen(
                        "http://127.0.0.1:3100/staff", timeout=1
                    ).status
                    == 200
                ):
                    break
            except (OSError, TimeoutError):
                time.sleep(0.2)
        else:
            raise RuntimeError("Browser-test frontend failed to become ready.")

    @classmethod
    def stop_frontend(cls):
        if cls.frontend.poll() is None:
            os.killpg(cls.frontend.pid, signal.SIGTERM)
            cls.frontend.wait(timeout=10)
        cls.log.close()

    def test_login_create_search_and_mobile_layout(self):
        company = make_company("Browser Test University", country="Nigeria")
        admin = make_user(
            "browser-admin@example.test",
            password="Browser-test-only-93284",
            is_superuser=True,
        )
        make_employee(company=company, user=admin, email="browser-admin@example.test")
        target = make_employee(
            company=company,
            email="promotion-browser@example.test",
            date_joining=date(2018, 1, 1),
        )
        StaffProfile.objects.create(
            employee=target, category="teaching", rank="Lecturer II"
        )
        policy = UniversityPolicy.objects.create(
            company=company,
            module="promotions",
            version=POLICY_VERSION,
            configuration=deepcopy(DEFAULTS["promotions"]),
        )
        adopt_policy(admin, policy.pk)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
                headless=True,
                args=["--no-sandbox"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.goto("http://127.0.0.1:3100/staff")
            expect(
                page.get_by_role("heading", name="Sign in to view your people")
            ).to_be_visible()
            page.get_by_role("link", name="Sign in securely").click()
            page.locator('input[name="username"]').fill("browser-admin@example.test")
            page.locator('input[name="password"]').fill("Browser-test-only-93284")
            page.locator('button[type="submit"]').click()
            expect(page.get_by_role("heading", name="Staff directory")).to_be_visible(
                timeout=15000
            )
            expect(page.get_by_role("button", name="Add staff member")).to_be_visible()
            page.get_by_role("button", name="Add staff member").click()
            page.get_by_label("First name", exact=True).fill("Amina")
            page.get_by_label("Last name", exact=True).fill("Okafor")
            page.get_by_label("Work email", exact=True).fill(
                "amina-browser@example.test"
            )
            page.get_by_label("Phone number", exact=True).fill("+2348012345678")
            page.get_by_label("Staff number", exact=True).fill("UNI-BROWSER-001")
            page.get_by_label("Staff category", exact=True).select_option(
                "non_teaching"
            )
            page.get_by_role("button", name="Create staff record", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text(
                "Staff record created", timeout=15000
            )
            expect(
                page.get_by_role("cell", name="UNI-BROWSER-001", exact=True)
            ).to_be_visible()
            page.get_by_label("Search staff", exact=True).fill("UNI-BROWSER-001")
            page.get_by_role("button", name="Search", exact=True).click()
            expect(page.get_by_text("1 staff member", exact=True)).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.get_by_role("heading", name="Staff directory")).to_be_visible()
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"), 390
            )
            page.screenshot(path="/tmp/university-staff-mobile.png", full_page=True)
            page.get_by_role("link", name="Amina Okafor", exact=True).click()
            expect(
                page.get_by_role("heading", name="Amina Okafor", exact=True)
            ).to_be_visible()
            stale_page = page.context.new_page()
            stale_page.goto(page.url)
            stale_page.get_by_label("Rank / designation", exact=True).fill("Professor")
            stale_page.get_by_label("Reason for change", exact=True).fill(
                "A stale edit must not overwrite newer information"
            )
            page.get_by_label("Rank / designation", exact=True).fill("Lecturer I")
            page.get_by_label("Reason for change", exact=True).fill(
                "Approved university designation correction"
            )
            page.get_by_role("button", name="Save changes", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text("Staff details updated")
            stale_page.get_by_role("button", name="Save changes", exact=True).click()
            expect(
                stale_page.get_by_role("alert").filter(has_text="This record changed")
            ).to_contain_text("This record changed")
            stale_page.get_by_role(
                "button", name="Reload latest record", exact=True
            ).click()
            expect(
                stale_page.get_by_label("Rank / designation", exact=True)
            ).to_have_value("Lecturer I")
            stale_page.close()
            page.get_by_role("button", name="Archive staff", exact=True).click()
            page.get_by_label("Reason for status change", exact=True).fill(
                "Employment ended after an approved review"
            )
            page.get_by_role("button", name="Confirm archive", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text(
                "archived and login access disabled"
            )
            page.get_by_role("button", name="Restore staff", exact=True).click()
            page.get_by_label("Reason for status change", exact=True).fill(
                "Record reinstated; login remains separately restricted"
            )
            page.get_by_role("button", name="Confirm restore", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text(
                "Login access remains disabled"
            )
            expect(
                page.get_by_text(
                    "Approved university designation correction", exact=True
                )
            ).to_be_visible()
            expect(page.get_by_text("Restored", exact=True)).to_be_visible()
            expect(page.get_by_text("Active → Archived", exact=True)).to_be_visible()
            page.screenshot(
                path="/tmp/university-staff-profile-mobile.png", full_page=True
            )
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"), 390
            )
            page.goto("http://127.0.0.1:3100/promotions")
            expect(
                page.get_by_role("heading", name="Staff promotions", exact=True)
            ).to_be_visible()
            page.get_by_label("Find staff", exact=True).fill(
                "promotion-browser@example.test"
            )
            expect(
                page.get_by_label("Staff member", exact=True).locator("option")
            ).to_have_count(2)
            page.get_by_label("Staff member", exact=True).select_option(str(target.pk))
            page.get_by_label("Adopted promotion policy", exact=True).select_option(
                str(policy.pk)
            )
            page.get_by_label("Proposed rank", exact=True).select_option("Lecturer I")
            page.get_by_label("Effective date", exact=True).fill(
                date.today().isoformat()
            )
            page.get_by_label("Evidence and justification", exact=True).fill(
                "Synthetic browser promotion evidence."
            )
            page.get_by_role("button", name="Submit for review", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text(
                "saved and recorded", timeout=15000
            )
            expect(
                page.locator("section p").filter(
                    has_text="Synthetic browser promotion evidence."
                )
            ).to_be_visible()
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"), 390
            )
            page.screenshot(
                path="/tmp/university-promotions-mobile.png", full_page=True
            )
            page.goto("http://127.0.0.1:3100/staff")
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(
                page.get_by_role("heading", name="Sign in to view your people")
            ).to_be_visible()
            browser.close()

        self.assertEqual(
            PromotionRequest.objects.get(employee=target).status, "submitted"
        )
        employee = Employee.objects.entire().get(email="amina-browser@example.test")
        self.assertFalse(employee.employee_user_id.has_usable_password())
        self.assertEqual(employee.university_profile.category, "non_teaching")
        self.assertEqual(employee.university_profile.rank, "Lecturer I")
        self.assertTrue(employee.is_active)
        self.assertFalse(employee.employee_user_id.is_active)
        self.assertEqual(
            set(
                StaffChange.objects.filter(employee=employee).values_list(
                    "action", flat=True
                )
            ),
            {"created", "updated", "archived", "restored"},
        )
        self.assertTrue(
            StaffChange.objects.filter(employee=employee, actor=admin).exists()
        )
