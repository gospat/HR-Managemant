# Bells University production release

**Status: development works; production acceptance is incomplete. Do not import real staff records or expose this stack to the Internet yet.** The target is Bells University of Technology, Nigeria, at least 10,000 teaching and non-teaching staff, standalone operation, MySQL, and eventual DigitalOcean hosting. All HR modules must be accepted before launch. The user identifies the Registrar as the approval authority; official salary, leave and promotion policies are not available yet.

## Deployment foundation

`deploy/university/compose.yml` separates MySQL 8.4, authenticated Redis, a one-shot migration/static-assets release job, Gunicorn, one scheduler, Next.js standalone, and an unprivileged TLS reverse proxy. Database, cache and application ports are not published. Only the edge has a loopback binding by default. Application containers run without Linux capabilities and with a read-only root filesystem. Image bases are pinned by digest. Runtime passwords are file-mounted, excluded from Git and Docker build context, and never embedded in image layers.

The hardened settings require explicit hosts, HTTPS origins, strong secrets, authenticated cache, a non-root MySQL login, and verified TLS for external MySQL. Cookies are secure and HTTP-only, sessions expire after 30 minutes of inactivity, sensitive responses prohibit caching, public setup/demo routes are disabled, and the edge overwrites forwarded headers. Readiness verifies a database query, a cache round trip and a recent scheduler heartbeat. Run exactly one scheduler; APScheduler does not support multiple competing schedulers against this job store. Alert on missed/error jobs, container restarts and stale readiness, not just process uptime.

### Local isolated staging

From the repository root, with Docker/Compose, Python 3 and OpenSSL installed:

```sh
python scripts/production_config.py --domain hr.test --directory .production-staging --test-certificate
docker compose --env-file .production-staging/compose.env -f deploy/university/compose.yml build
docker compose --env-file .production-staging/compose.env -f deploy/university/compose.yml up -d
docker compose --env-file .production-staging/compose.env -f deploy/university/compose.yml ps
```

The generator refuses nonempty directories. It generates random local secrets and an explicitly **pending** acceptance manifest. Test certificates are restricted to `.test` staging names, valid for two days. Verify TLS using that certificate as an explicit trust anchor; never disable certificate verification. A live installation needs a university-controlled DNS name, a publicly trusted certificate, renewal monitoring, and a reviewed firewall. The `HR_BIND_ADDRESS` default must remain loopback until those prerequisites are in place.

Secrets are owner/group readable (0640), inside an owner-only configuration directory (0700). `HR_SECRET_GID` supplies the restricted group to non-root containers; protect group membership on the deployment host. Keep the directory outside shared workspaces in a real deployment. Do not run `compose config` without `--quiet` when configuration may contain credentials. Do not expose Gunicorn directly: it trusts forwarded protocol headers from the isolated edge.

Bootstrap the first administrator interactively, without a password in shell history:

```sh
docker compose --env-file .production-staging/compose.env -f deploy/university/compose.yml exec backend python manage.py bootstrap_university --name 'Bells University of Technology' --admin-email YOUR_AUTHORIZED_ADMIN_EMAIL
```

For cloud builds behind an inspecting proxy, pass existing proxy environment bindings as Docker predefined proxy arguments, and mount the environment's trusted CA bundle as BuildKit secret `build_ca`. The Dockerfiles accept this optional CA for package downloads; verification stays enabled and the bundle is not retained in the resulting image. Ordinary DigitalOcean builds do not require this cloud-specific configuration.

## Launch gate and acceptance evidence

`HR_DEPLOYMENT_STAGE=production` is currently explicitly blocked by unresolved implementation defects listed below. After those defects are fixed and the guard is removed in a reviewed change, startup also requires an acceptance manifest matching the image's exact `HR_SOURCE_REVISION`. Every module and operational requirement needs `status: accepted`, a relative evidence file and its SHA-256 digest. Evidence must stay within the acceptance directory. The manifest must name the university, cover at least 10,000 staff records, identify an authorized reviewer and have a timezone-aware approval date. Hash checks detect changed evidence; they do **not** authenticate a reviewer or substitute for university governance. Restrict write access and archive the signed approval record separately. Never set items accepted just to start a server.

Required modules: staff, recruitment, onboarding, leave, attendance, payroll, promotions, performance, offboarding, documents, reports, assets, helpdesk, projects and meetings. Required operational acceptance: security review, backup/restore, load test, disaster recovery and data protection. The generated manifest contains every required item as pending. Development regression tests validate the new staff functionality; they do not establish correctness of every inherited module.

Acceptance must exercise real roles and forbidden actions: employee self-service, departmental/faculty approvers, HR, payroll, auditors and system administrators. Check teaching versus non-teaching grades, contract types, delegation, concurrent changes, bulk actions, exports, rejected requests and offboarding access revocation. Promotions need an explicit workflow implementation and university-approved eligibility/approval rules; inherited performance tools are not proof of a promotion module.

## Confirmed blockers

* The Python dependency audit reports CVE-2025-26240 / PYSEC-2026-2860 in `pdfkit==1.0.0`, with no patched version. Hardened staging/production disables the shared PDF renderer configuration, and the runtime image intentionally omits wkhtmltopdf. PDF exports remain unavailable until a supported isolated renderer replaces it and payslip/document output is tested. The audit is **not clean**. The university CI dependency-audit job deliberately fails until the vulnerable dependency is removed; the advisory is not waived.
* Upstream media access does not establish file ownership for every HR module. Hardened settings restrict non-logo media to superusers. Implement and test employee/document/company/approver authorization before ordinary-user document acceptance; this restriction is a functional blocker, not completion of document management.
* Nigerian payroll rules, PAYE tables, pension and other deductions, salary scales, allowances, arrears, rounding, audit/reversal procedures and the university's approval hierarchy have not been provided or accepted. Do not infer them from generic payroll defaults. Obtain approved reference calculations for teaching and non-teaching staff and reconcile results before paying anyone.
* University leave entitlements, academic calendars, accrual/carryover, attendance exceptions, promotion criteria, retention periods remain unspecified. Registrar sign-off is required; the authorized reviewer’s name and email remain to be supplied.
* No DigitalOcean account, live DNS/certificate, production database or external backup destination has been configured. Container templates and local checks do not validate those services.

## DigitalOcean deployment and capacity

Start with a private VPC and separate staging/production projects. Use a DigitalOcean managed MySQL service with a least-privilege application user, connection limits, automated backups and CA/hostname-verified TLS (`MYSQL_SSL_CA`). The supplied Compose MySQL service is an isolated staging/reference single-host database, not a claim of highly available production hosting. Adapt the private runtime connection and mount the provider CA before using a managed service; remove the local MySQL dependency from the deployment override. Use private network paths for app/cache/database, a trusted TLS edge or load balancer, and a firewall restricting administrative access.

The supplied media volume is persistent on one host but is not shared storage or an off-host backup. For multiple app hosts, provide private shared/object storage with per-file authorization; never make staff uploads a public bucket. Ensure proxy trust settings match the actual number of trusted hops when adding a load balancer. Provide SMTP with delivery monitoring for password resets and workflow notifications; no mail server is configured here. Disable unneeded third-party/biometric integrations until reviewed.

10,000 staff records is not 10,000 concurrent requests. Establish expected concurrent users, busiest workflows, bulk imports, payroll batch size and required response times. Populate at least 10,000 synthetic staff records in an isolated staging database; measure authenticated directory/search, role-scoped dashboards, approvals, exports and full payroll runs at peak concurrency. Record p50/p95/p99 latency, errors, database connections, slow queries, CPU/RAM and scheduler lag. Tune worker counts, indexes and database/cache sizing from results. The default two Gunicorn workers are a starting configuration, not a capacity guarantee. No 10,000-staff workload acceptance has been completed.

## Backups, recovery and operations acceptance

Before launch, automate encrypted, off-host backups of **both MySQL and media**, retain the matching application image/revision and securely escrow recovery keys separately. Use MySQL-consistent backups (`mysqldump --single-transaction --routines --triggers --events --no-tablespaces` for logical dumps with suitable backup privileges) and a maintenance window or coordinated storage snapshots when cross-file/database consistency is required. The developer `university_dev.py backup` is a local convenience snapshot, not a production backup service. Agree RPO, RTO, retention, residency and deletion requirements with the university's data protection officer under applicable Nigerian data protection obligations.

Restore into an isolated empty database and media location, never over a running production instance. Verify row counts and representative HR records, login/permissions, documents, payroll totals and audit history with the matching release. Test recovery from total host loss and missing credentials/keys. Store measured restore time and verifier sign-off in the acceptance evidence. Alert on backup age, failed jobs, disk space, TLS expiry, dependency advisories, database saturation and application errors. Logs must omit credentials and staff/payroll payloads; restrict access and configure retention.

For upgrades: back up and verify restore first, rehearse migrations on a production-sized copy, deploy immutable images identified by commit/digest, run the release job once, then perform smoke tests and approval checks before opening traffic. Database migrations may be irreversible; an old application image alone is not a rollback plan. Rehearse database/media restoration or a compatible forward fix. Do not delete Docker volumes to upgrade.

## Verification in this cloud environment

The application regression suite passed 97 tests, the production boundary/PDF safety suite passed, and the separate real Chromium staff-management journey passed. The frontend build, TypeScript check and native standalone HTTP startup passed. Both runtime images built successfully with TLS verification enabled. A fresh Compose MySQL installation completed all migrations, collected static assets and started Gunicorn, Redis, Next.js, the TLS edge and the dedicated scheduler. Certificate-verified HTTPS smoke checks passed for the frontend, security headers, blocked initialization/readiness routes and anonymous staff access. Removing the stopped scheduler's heartbeat caused readiness to fail; restarting the scheduler restored readiness.

`manage.py check --deploy` produced one warning: HSTS preload is intentionally false pending a university domain-owner decision. It reported no other deployment-check issues. Existing upstream startup database-query and duplicate static asset warnings remain visible. The Python audit failed on the unpatched pdfkit advisory; the frontend production dependency audit found zero reported vulnerabilities. These checks establish a tested staging foundation, not full HR-module acceptance, live DigitalOcean readiness or 10,000-staff workload validation. No live deployment was performed.
