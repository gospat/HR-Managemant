# University HR development environment

A standalone Nigerian university HR development foundation using MySQL 8.4,
Django 5.2 and Next.js 16 / React / TypeScript. It is a local derivative of
Horilla stable branch `2.0`, starting at commit
`9c97e785f505a6dc2feae2312609ee28f32993b0`. Original LGPL license and notices
are retained. `origin` remains `gospat/HR-Managemant`; `upstream` points to
`horilla-opensource/horilla`. This is a development release; production deployment has not been performed.

## What is implemented

- Next.js landing page and authenticated staff directory at `/staff`.
- Staff search, category filtering and pagination (25 records per page).
- Staff profile pages at `/staff/<id>` with editable contact/employment details.
  Email, institution and account privileges cannot be edited through this form.
- Mandatory change reasons, database row locks and opaque revision checks reject
  stale edits, including changes made in the inherited Horilla screens.
- Archiving disables the linked login and invalidates its existing sessions.
  Restore employment records separately from login access. Explicit login
  restoration needs a separate permission and an already configured password.
- Protected self/privileged accounts and staff with management/workflow
  responsibilities cannot be archived through this flow.
- Authorized, paginated audit history records actors, reasons and before/after
  values for edits, archival and restoration.
- Staff registration with teaching/non-teaching classification, faculty or
  directorate, department, staff number and rank.
- HR view/create permissions, institution scope derived from the authenticated
  employee, session authentication, CSRF protection and private/no-store API responses.
- Atomic registration and audit records identifying the user making each change.
- Newly registered staff receive no usable password. An administrator must
  activate access through a secure password-setting process; no predictable
  default passwords are used.
- University-specific Django app in `university/people`, separated into models,
  serializers, services, views, administration and tests.
- Idempotent institution setup and optional administrator provisioning.

Existing Horilla recruitment, leave, attendance, payroll and performance modules
remain available through the proxy using their original interface. They have
not all been rebuilt in React or comprehensively validated. Generic payroll
is **not** a verified implementation of Nigerian statutory payroll.

## Setup

Use the existing `/workspace/HR-Managemant` checkout. Cloud tasks are already
isolated; do not create a worktree. Python 3.12, Node 24, npm, uv, Docker, GCC
and the system MariaDB client shared library were available in this machine.

```bash
cd /workspace/HR-Managemant
bash scripts/install-university.sh
python scripts/university_dev.py db
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py migrate --noinput
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py collectstatic --noinput
```

The install script preserves `.env`, generates private local credentials if it
is absent, installs the hash-locked Python requirements and npm lockfile, and
builds/type-checks the frontend. It preserves package/TLS verification. Where
MySQL build headers are missing, the cloud fallback extracts authenticated
Debian packages into ignored `.university-setup/`, without modifying the system.
On other development machines, install MySQL client development headers through
the OS package manager instead.

`university.env.example` lists application settings without secret values. Never
commit `.env`, backups, uploads or real staff data. The local development `.env`
uses DEBUG=True and loopback access; it is not a production configuration.

MySQL uses container and volume `university-hr-mysql`, loopback port 3306, and
a pinned official image digest. The helper prepares access only to the selected
local development database and its corresponding test database. It does not
replace existing credentials. Failed compatibility attempts are preserved in
unused development schemas; the current connection is selected by `.env`.

## Start the development workflow

In separate terminals from the repository root:

```bash
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py run_scheduler
npm --prefix frontend run start
```

For frontend hot reload, use `npm --prefix frontend run dev` instead of `start`.
Do not start both on port 3000. Backend readiness is `/ready/`; verify database
and scheduler both report `ok`. Check `/university-api/session/` through the
frontend proxy, then verify the `/staff` sign-in screen. A PID or open port alone
does not establish readiness. Frontend rewrites preserve Django trailing slashes.
If using a nondefault HR_BACKEND_URL, set it **before building** as well as when
starting Next.js. CSRF_TRUSTED_ORIGINS must contain the actual frontend origin.

No production administrator or real employee was invented. Create the institution
with its actual name (maximum 50 characters) and your administrator email:

```bash
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py bootstrap_university --name "Your University" --admin-email your-admin@example.edu.ng
```

This prompts for a password in an interactive terminal. For automated use,
supply DJANGO_SUPERUSER_PASSWORD securely through the process environment,
not a command argument or chat. Password validation applies. Existing users are
never silently promoted or overwritten. The administrator receives a linked
employee record, required by Horilla login. Update its clearly marked placeholder
name and phone after signing in. A placeholder institution named `University`
was created for environment validation; rename it rather than creating duplicates.
For idempotent institution setup without an administrator, omit `--admin-email`.

Manage faculties/directorates through Django administration. Assign ordinary HR
users the employee view/add permissions; editing also requires
`employee.change_employee`. They remain limited to their own institution.
Status changes require `university_people.change_staff_status`, access restoration
also requires `university_people.restore_staff_login`, and audit history requires
`university_people.view_staff_history` plus staff-view access. Grant these
permissions deliberately to HR roles; a regular editor receives none implicitly.
University extension administration is restricted to superusers.

Edits to names, phone, staff number, department, faculty, category or rank require
a reason. Institution transfers, email/account changes and password setting are
separate administrative actions. Restoring a record without checking “Also restore
login access” deliberately keeps the account disabled. Audit entries contain
sensitive staff information and are available only to authorized history viewers.
If a record changed elsewhere, reload its latest version before saving again.

## Validation

```bash
bash scripts/test-university.sh
```

The selected 97 regression tests cover MySQL indexes and duplicate rejection,
null-key semantics, staff creation, rollback, unauthorized/cross-institution
access, CSRF, filtering, login lockout, account archival, bootstrap safeguards,
holiday validation, payroll component conditions, staff edits, conflicting revisions,
status transitions, protected accounts and scoped audit history. They passed on MySQL.
Django checks and migration/model drift checks passed. Frontend production build
and strict TypeScript checks passed. Do not interpret this as testing every
upstream HR module or Nigerian payroll compliance.

Optional real Chromium journey:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv pip install --python .venv/bin/python --require-hashes -r requirements-university-dev.lock
DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py test university.people.tests.test_browser --keepdb --noinput
```

This launches a separate Next.js development server on port 3100 against Django's
isolated test database. It exercises real login, non-teaching registration,
search, editing, stale-edit rejection across browser tabs, archival/restoration,
mobile overflow and sign-out. It requires system Chromium (or CHROMIUM_PATH).
Run it separately from the API suite; its live-server test flushes test data.
Test credentials are synthetic and confined to the test database.

Optional face-detection/geofencing apps are not installed or required by this
workflow. Login now correctly handles their absence. Upstream currently emits
an app-initialization database-query warning and collectstatic reports duplicate
asset names; neither was silenced. The tested login and directory are the
functional readiness evidence.

## Backup and restoration

```bash
python scripts/university_dev.py backup
python scripts/university_dev.py restore --database empty_restore_database
```

The private, ignored snapshot is `.university-setup/database.sql`. Restore refuses
a nonempty database. `db` automatically restores this snapshot only if the
selected local database is empty. A restore into a separate database was tested;
table, migration and institution counts matched. Do not assume Docker volumes
survive cloud publication. This verifies local restoration, not restoration in
a new published cloud task. Back up again after intentional development changes.
A real deployment needs encrypted, off-machine backups and rehearsed recovery.

## MySQL compatibility patches

Fresh MySQL setup previously failed before the application could start. This
new, undeployed derivative adjusts bootstrap migrations alongside the models:

- Company address is VARCHAR(255), matching its declared length and allowing
  full composite uniqueness with the institution name.
- Non-null badge/company rules use ordinary unique indexes: MySQL permits
  multiple NULL keys, preserving the original conditional semantics.
- Global export singleton and holiday rules use CASE expression unique indexes;
  company-specific uniqueness is retained. Tests bypass model validation to
  prove the database itself rejects duplicates.
- Allowance rule field/condition/basis lengths are 128/20/32, fitting the complete
  composite index under MySQL's 3072-byte key limit. Existing choice values fit.
- Automation titles are limited to 255 characters through a new normal migration.

Do not apply these edited historical migrations to an existing deployed Horilla
installation without a separate migration/upgrade plan. Never fake a migration
or disable constraints to make installation appear successful. Future upstream
merges must review these explicit compatibility patches.

## Remaining production work

See [current production-readiness evidence and blockers](PRODUCTION-READINESS.md).
The setup requires `fonts-dejavu-core` for bounded Unicode document exports.
The installer synchronizes the hash-locked runtime environment so removed vulnerable
packages cannot remain installed after an upgrade. Browser tests require the
separate locked development requirements.

University promotion committees, sabbatical/study-leave policies, salary
structures such as applicable CONUASS/CONTISS variants, current Nigerian PAYE,
pensions and institution-specific deductions require requirements and payroll
expert review. No rates or compliance claims have been invented.

Before using real staff data: configure the actual institution, permissions,
HTTPS, production secrets, DEBUG=False, secure storage, shared cache for multiple
workers, backup retention, monitoring and a production process supervisor. Run
representative load tests, a data-protection review and end-to-end acceptance of
all required HR modules. This delivery is a tested first development release,
not a completed production university HR system.


### University governance templates

After migrations, run `DJANGO_SETTINGS_MODULE=university.settings .venv/bin/python manage.py seed_university_policies --company INSTITUTION_ID` for the correct existing company ID. See [production readiness](PRODUCTION-READINESS.md#provisional-university-policy-templates-and-promotion-operations) for roles, policy review/adoption and `/promotions`. Seeding creates provisional drafts, not Registrar approval. Leave/attendance templates require separate operational module configuration; promotion policy is enforced by the new workflow. Salary/statutory tables must be configured from validated sources.


### Broader HR validation

Run `bash scripts/test-university-modules.sh` for inherited HR modules, reports, audit and bulk imports on MySQL, separately from the browser suite. Generic modal/import/bulk callbacks require authenticated shared Redis in production; their opaque session-bound links expire after 30 minutes. Reopen expired forms. Leave email delivery starts after commit and requires configured SMTP plus operational monitoring.
