# University HR development release

This release establishes a standalone Nigerian university HR development
foundation based on Horilla, with MySQL 8.4, Django and a Next.js/React/TypeScript
portal. It is not a completed production university HR system.

## Delivered

- MySQL compatibility patches with database-level uniqueness checks retained.
- Teaching/non-teaching staff registration, search, pagination and profile editing.
- Institution-scoped permissions, CSRF protection and secure session sign-out.
- Archiving that revokes access, and restoration with separate login permissions.
- Mandatory change reasons, stale-edit protection and protected change history.
- Reusable installation, startup, backup and restoration helpers.

## Verified

97 regression tests passed, along with Django checks, migration consistency,
the frontend production build and strict TypeScript checks. A real Chromium
journey verified login, registration, search, editing, conflicting browser tabs,
archival/restoration, mobile layout and sign-out. Development database snapshot
restoration was verified separately.

## Still required

Nigerian statutory payroll and institution-specific salary structures, promotion
and leave policies, comprehensive acceptance of inherited HR modules, production
configuration, load testing and a real university administrator remain outstanding.
Existing Horilla modules retain their original interface; they have not all been
rebuilt in React or comprehensively tested.

Read [setup and administrator instructions](UNIVERSITY-SETUP.md) before use.
Edited historical migrations are intended for this new derivative and need a
separate upgrade plan before application to an existing deployed Horilla system.
