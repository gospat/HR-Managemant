import hashlib
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from django.http import HttpResponse
from django.test import SimpleTestCase, RequestFactory
from university.operations.acceptance import (
    acceptance_errors,
    INSTITUTION,
    MODULES,
    OPERATIONS,
)
from university.operations.config import production_errors, prepare_environment
from university.operations.health import readiness
from university.operations.middleware import ProductionBoundaryMiddleware


class AcceptanceTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "release.json"
        evidence = self.path.parent / "evidence.txt"
        evidence.write_text("Synthetic test evidence only, not university approval.")
        entry = dict(
            status="accepted",
            evidence=evidence.name,
            sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        )
        self.revision = "a" * 40
        self.manifest = dict(
            schema_version=1,
            institution=INSTITUTION,
            source_revision=self.revision,
            target_staff_count=10000,
            approved_by=dict(
                name="Test Reviewer", role="Registrar", email="reviewer@invalid.test"
            ),
            approved_at="2026-01-01T00:00:00+00:00",
            modules={key: dict(entry) for key in MODULES},
            operations={key: dict(entry) for key in OPERATIONS},
        )

    def validate(self):
        self.path.write_text(json.dumps(self.manifest))
        return acceptance_errors(self.path, self.revision)

    def test_complete_evidence_is_validated(self):
        self.assertEqual(self.validate(), [])

    def test_release_revision_must_match(self):
        self.manifest["source_revision"] = "b" * 40
        self.assertTrue(any("commit" in e for e in self.validate()))

    def test_registrar_approval_is_required(self):
        self.manifest["approved_by"]["role"] = "HR officer"
        self.assertTrue(any("Registrar" in e for e in self.validate()))

    def test_every_module_is_required(self):
        for key in MODULES:
            with self.subTest(module=key):
                entry = self.manifest["modules"].pop(key)
                self.assertTrue(any("modules." + key in e for e in self.validate()))
                self.manifest["modules"][key] = entry

    def test_evidence_tampering_and_traversal_are_rejected(self):
        for name in ("../evidence.txt", "/etc/passwd", "missing", 123):
            with self.subTest(evidence=name):
                self.manifest["modules"]["payroll"]["evidence"] = name
                self.assertTrue(any("modules.payroll" in e for e in self.validate()))

    def test_invalid_manifest_and_review_date_fail_closed(self):
        for value in (None, [], 12):
            self.path.write_text(json.dumps(value))
            self.assertTrue(acceptance_errors(self.path, self.revision))
        self.manifest["approved_at"] = None
        self.assertTrue(any("date" in e for e in self.validate()))


class ConfigurationTests(SimpleTestCase):
    def config(self):
        return dict(
            DEBUG="false",
            SECRET_KEY="x" * 64,
            DB_INIT_PASSWORD="y" * 48,
            DATABASE_URL="mysql://hr:password@mysql/hr",
            REDIS_URL="redis://:password@redis/1",
            ALLOWED_HOSTS="hr.test",
            CSRF_TRUSTED_ORIGINS="https://hr.test",
            HR_PUBLIC_URL="https://hr.test",
            HR_DEPLOYMENT_STAGE="staging",
        )

    def test_staging_requires_secure_explicit_configuration(self):
        self.assertEqual(production_errors(self.config()), [])
        for key, value in [
            ("DEBUG", "true"),
            ("SECRET_KEY", "short"),
            ("ALLOWED_HOSTS", "*"),
            ("DATABASE_URL", "mysql://root:password@mysql/hr"),
            ("REDIS_URL", "redis://redis/1"),
            ("CSRF_TRUSTED_ORIGINS", "http://hr.test"),
        ]:
            with self.subTest(key=key):
                config = self.config()
                config[key] = value
                self.assertTrue(production_errors(config))

    def test_external_database_requires_verified_tls(self):
        config = self.config()
        config["DATABASE_URL"] = "mysql://hr:password@db.ondigitalocean.com/hr"
        self.assertTrue(any("TLS" in e for e in production_errors(config)))
        config = self.config()
        config["REDIS_URL"] = "redis://:password@cache.ondigitalocean.com/1"
        self.assertTrue(any("rediss" in e for e in production_errors(config)))

    def test_malformed_urls_are_rejected_without_exposing_credentials(self):
        for key in ("DATABASE_URL", "REDIS_URL", "HR_PUBLIC_URL"):
            config = self.config()
            config[key] = "https://private-password@[invalid"
            errors = production_errors(config)
            self.assertTrue(errors)
            self.assertNotIn("private-password", " ".join(errors))

    def test_production_cannot_bypass_university_acceptance(self):
        config = self.config()
        config["HR_DEPLOYMENT_STAGE"] = "production"
        self.assertTrue(any("manifest" in e for e in production_errors(config)))

    def test_secret_files_and_password_url_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.write_text("p@ss:/word")
            config = dict(
                MYSQL_PASSWORD_FILE=str(path),
                MYSQL_HOST="mysql",
                MYSQL_USER="hr",
                MYSQL_DATABASE="hr",
            )
            prepare_environment(config)
            self.assertIn("p%40ss%3A%2Fword@", config["DATABASE_URL"])


class BoundaryTests(SimpleTestCase):
    def test_vulnerable_pdf_renderer_is_disabled_in_hardened_runtime(self):
        from base.methods import pdfkit_configuration
        from django.core.exceptions import ImproperlyConfigured

        with self.settings(HR_DEPLOYMENT_STAGE="staging"):
            with self.assertRaises(ImproperlyConfigured):
                pdfkit_configuration()

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ProductionBoundaryMiddleware(
            lambda request: HttpResponse("ok")
        )

    def request(self, path, superuser=False):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=superuser)
        return self.middleware(request)

    def test_initialization_and_document_access_fail_closed(self):
        self.assertEqual(self.request("/initialize-database").status_code, 404)
        self.assertEqual(self.request("/media/payroll/private.pdf").status_code, 403)
        self.assertEqual(
            self.request("/media/payroll/private.pdf", True).status_code, 200
        )

    def test_sensitive_responses_are_not_cached(self):
        self.assertEqual(
            self.request("/university-api/staff/")["Cache-Control"], "private, no-store"
        )

    @patch("university.operations.health.connection")
    @patch("university.operations.health.cache")
    def test_readiness_requires_live_scheduler(self, cache, connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = [1]
        connection.cursor.return_value.__enter__.return_value = cursor
        for heartbeat, status in (
            (None, 503),
            (time.time() - 90, 503),
            (time.time(), 200),
        ):
            cache.get.side_effect = ["ok", heartbeat]
            response = readiness(self.factory.get("/ready/"))
            self.assertEqual(response.status_code, status)
