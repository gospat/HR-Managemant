#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SETTINGS_MODULE=university.settings
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test \
  university.people.tests.test_staff_api \
  university.people.tests.test_staff_management \
  university.people.tests.test_mysql_integrity \
  university.people.tests.test_bootstrap \
  employee.tests.test_employee_company \
  employee.tests.test_archive_revokes_login \
  base.tests.test_export_permission_seeding \
  base.tests.test_holiday_form \
  base.tests.test_login_bruteforce \
  payroll.tests.test_component_conditions \
  university.documents.tests \
  university.documents.test_access \
  university.documents.test_rules \
  university.governance.tests \
  university.documents.test_payslip_api \
  university.operations.tests \
  university.people.tests.test_scale \
  base.tests.test_pdf_xss_guard \
  core.tests.test_has_xss_bypass \
  --keepdb --noinput
npm --prefix frontend run build
npm --prefix frontend run typecheck
# Optional browser journey (requires requirements-university-dev.txt and Chromium):
# .venv/bin/python manage.py test university.people.tests.test_browser --keepdb --noinput
