#!/usr/bin/env python3
"""Offline Compose backup and authenticated recovery extraction; never overwrite a database."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from university.operations.backup import encrypt_bundle, extract_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["keygen", "create", "extract"])
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--config-directory", default=".production-staging")
    parser.add_argument("--output")
    parser.add_argument("--input")
    args = parser.parse_args()
    if args.action == "keygen":
        with Path(args.key_file).open("xb") as key:
            os.chmod(args.key_file, 0o600)
            key.write(os.urandom(32))
        print(
            "Private recovery key created. Keep a separate secure copy off the server."
        )
        return
    if not args.output:
        parser.error("--output is required")
    if args.action == "extract":
        if not args.input:
            parser.error("--input is required")
        extract_bundle(args.input, args.output, args.key_file)
        print(
            "Backup authenticated and extracted to a new private directory. No database was changed."
        )
        return
    configuration = Path(args.config_directory).resolve()
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(configuration / "compose.env"),
        "-f",
        str(ROOT / "deploy/university/compose.yml"),
    ]
    statuses = subprocess.check_output(
        compose + ["ps", "--status", "running", "--services"], text=True
    ).splitlines()
    if any(name in statuses for name in ("backend", "scheduler", "release", "edge")):
        parser.error(
            "Stop edge, backend, scheduler and any release job before backing up database and media."
        )
    if "mysql" not in statuses:
        parser.error(
            "The isolated MySQL service must be running for this backup adapter."
        )
    database_id = subprocess.check_output(
        compose + ["ps", "-q", "mysql"], text=True
    ).strip()
    health = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", database_id],
        text=True,
    ).strip()
    if health != "healthy":
        parser.error(
            "MySQL is not healthy yet; wait for its health check before backing up."
        )
    with tempfile.TemporaryDirectory(prefix="bells-backup-") as directory:
        private = Path(directory)
        dump = 'MYSQL_PWD="$(cat /run/secrets/mysql_password)" exec mysqldump -u university_hr --single-transaction --skip-lock-tables --no-tablespaces --routines --triggers --events university_hr'
        with (private / "database.sql").open("wb") as out:
            subprocess.run(
                compose + ["exec", "-T", "mysql", "sh", "-c", dump],
                stdout=out,
                check=True,
            )
        with (private / "media.tar").open("wb") as out:
            subprocess.run(
                compose
                + [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "backend",
                    "tar",
                    "-C",
                    "/app/media",
                    "-cf",
                    "-",
                    ".",
                ],
                stdout=out,
                check=True,
            )
        images = subprocess.check_output(
            compose + ["config", "--images"], text=True
        ).splitlines()
        image_name = next(
            name for name in images if name.startswith("university-hr-backend:")
        )
        image = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", image_name], text=True
            )
        )[0]
        hashes = {}
        for name in ("database.sql", "media.tar"):
            with (private / name).open("rb") as item:
                hashes[name] = hashlib.file_digest(item, "sha256").hexdigest()
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend_image": image["Id"],
            "source_revision": image["Config"]
            .get("Labels", {})
            .get("org.opencontainers.image.revision"),
            "sha256": hashes,
        }
        (private / "manifest.json").write_text(json.dumps(manifest, indent=2))
        encrypt_bundle(private, args.output, args.key_file)
    print(
        "Authenticated database/media backup created. Copy it off-host and perform a restore drill before launch."
    )


if __name__ == "__main__":
    main()
