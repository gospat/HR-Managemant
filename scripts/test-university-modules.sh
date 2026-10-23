#!/usr/bin/env bash
# Run inherited HR modules against the configured MySQL test database.
# Keep this separate from LiveServer/browser tests, which flush that database.
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SETTINGS_MODULE=university.settings
.venv/bin/python manage.py test \
  base employee payroll leave attendance recruitment onboarding pms \
  offboarding horilla_documents asset helpdesk project horilla_meet \
  report horilla_audit master_import \
  --keepdb --noinput
