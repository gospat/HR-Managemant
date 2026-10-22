#!/usr/bin/env python3
"""Generate private staging/deployment inputs; never approve a university release."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from university.operations.acceptance import INSTITUTION, MODULES, OPERATIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--directory", default=".production")
    parser.add_argument("--stage", choices=["staging", "production"], default="staging")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--test-certificate", action="store_true")
    args = parser.parse_args()
    if (
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", args.domain)
        or ".." in args.domain
    ):
        parser.error("Use a DNS hostname without a scheme, path or port.")
    if not 1 <= args.port <= 65535:
        parser.error("Invalid HTTPS port.")
    if args.test_certificate and (
        args.stage != "staging" or not args.domain.endswith(".test")
    ):
        parser.error("Test certificates are restricted to staging .test hostnames.")
    directory = Path(args.directory).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(directory.iterdir()):
        parser.error(
            "Configuration directory must be empty; existing secrets are never overwritten."
        )
    os.chmod(directory, 0o700)
    for name in ("secrets", "tls", "acceptance"):
        mode = 0o700 if name == "secrets" else 0o750
        (directory / name).mkdir(mode=mode)
        (directory / name).chmod(mode)

    def write(relative, value, mode=0o640):
        target = directory / relative
        target.write_text(value)
        target.chmod(mode)

    for name in (
        "django_key",
        "initialization_key",
        "mysql_password",
        "mysql_root_password",
        "redis_password",
    ):
        write("secrets/" + name, secrets.token_hex(48) + "\n")
    origin = (
        "https://" + args.domain + ("" if args.port == 443 else ":" + str(args.port))
    )
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    write(
        "compose.env",
        f"HR_CONFIG_DIR={directory}\nHR_SOURCE_REVISION={revision}\nHR_PUBLIC_URL={origin}\nHR_HTTPS_PORT={args.port}\nHR_BIND_ADDRESS=127.0.0.1\nHR_SECRET_GID={os.getgid()}\n",
    )
    write(
        "runtime.env",
        "\n".join(
            [
                "DJANGO_SETTINGS_MODULE=university.production",
                "DEBUG=false",
                f"HR_DEPLOYMENT_STAGE={args.stage}",
                f"HR_PUBLIC_URL={origin}",
                f"ALLOWED_HOSTS={args.domain}",
                f"CSRF_TRUSTED_ORIGINS={origin}",
                "SECRET_KEY_FILE=/run/secrets/django_key",
                "DB_INIT_PASSWORD_FILE=/run/secrets/initialization_key",
                "MYSQL_PASSWORD_FILE=/run/secrets/mysql_password",
                "REDIS_PASSWORD_FILE=/run/secrets/redis_password",
                "MYSQL_HOST=mysql",
                "MYSQL_DATABASE=university_hr",
                "MYSQL_USER=university_hr",
                "REDIS_HOST=redis",
                "HR_ACCEPTANCE_FILE=/run/acceptance/release.json",
            ]
        )
        + "\n",
    )
    manifest = dict(
        schema_version=1,
        institution=INSTITUTION,
        source_revision=revision,
        target_staff_count=10000,
        approved_by={"role": "Registrar"},
        approved_at=None,
        modules={name: {"status": "pending"} for name in MODULES},
        operations={name: {"status": "pending"} for name in OPERATIONS},
    )
    write("acceptance/release.json", json.dumps(manifest, indent=2) + "\n")
    write(
        "nginx.conf",
        (ROOT / "deploy/university/nginx.conf.template")
        .read_text()
        .replace("__DOMAIN__", args.domain),
    )
    if args.test_certificate:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-noenc",
                "-keyout",
                str(directory / "tls/privkey.pem"),
                "-out",
                str(directory / "tls/fullchain.pem"),
                "-days",
                "2",
                "-subj",
                f"/CN={args.domain}",
                "-addext",
                f"subjectAltName=DNS:{args.domain}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        (directory / "tls/privkey.pem").chmod(0o640)
        (directory / "tls/fullchain.pem").chmod(0o640)
    print(
        f"Private configuration generated in {directory}. University acceptance is PENDING."
    )
    if not args.test_certificate:
        print(
            "Install a trusted fullchain.pem and privkey.pem in tls/ before starting."
        )


if __name__ == "__main__":
    main()
