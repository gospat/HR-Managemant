#!/usr/bin/env python3
"""Local development database provisioning. Never prints credential values."""

import argparse
import os
import re
from pathlib import Path
import secrets
import subprocess
import time
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
CONTAINER = "university-hr-mysql"
IMAGE = (
    "mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69"
)


def read_env():
    return dict(
        line.split("=", 1)
        for line in ENV.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )


def initialize():
    if ENV.exists():
        print("Preserved existing .env.")
        return
    password = secrets.token_urlsafe(32)
    values = {
        "DJANGO_SETTINGS_MODULE": "university.settings",
        "DEBUG": "True",
        "ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
        "CSRF_TRUSTED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
        "TIME_ZONE": "Africa/Lagos",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "DB_INIT_PASSWORD": secrets.token_urlsafe(32),
        "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "DATABASE_URL": f"mysql://university_hr:{quote(password)}@127.0.0.1:3306/university_hr",
    }
    fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    print("Generated a private local .env; no credentials were printed.")


def database():
    initialize()
    values = read_env()
    url = urlsplit(values["DATABASE_URL"])
    if (
        url.scheme != "mysql"
        or url.hostname not in ["localhost", "127.0.0.1"]
        or url.port != 3306
    ):
        raise SystemExit(
            "This helper supports only the local MySQL development instance on port 3306."
        )
    exists = (
        subprocess.run(
            ["docker", "container", "inspect", CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    if exists:
        subprocess.run(
            ["docker", "start", CONTAINER], check=True, stdout=subprocess.DEVNULL
        )
    else:
        if not values.get("MYSQL_ROOT_PASSWORD"):
            raise SystemExit(
                "Existing .env lacks MYSQL_ROOT_PASSWORD. Restore the original database container or securely configure local database credentials; existing files were preserved."
            )
        # Passing the file through stdin keeps values out of command arguments.
        docker_env = (
            "\n".join(
                [
                    f"MYSQL_ROOT_PASSWORD={values['MYSQL_ROOT_PASSWORD']}",
                    f"MYSQL_DATABASE={url.path.lstrip('/')}",
                    f"MYSQL_USER={unquote(url.username or '')}",
                    f"MYSQL_PASSWORD={unquote(url.password or '')}",
                ]
            )
            + "\n"
        )
        # Docker CLI --env-file cannot read stdin portably; use a private,
        # short-lived file and remove it immediately after container creation.
        import tempfile

        fd, filename = tempfile.mkstemp(prefix="university-mysql-", suffix=".env")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(docker_env)
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    CONTAINER,
                    "--env-file",
                    filename,
                    "-p",
                    "127.0.0.1:3306:3306",
                    "-v",
                    "university-hr-mysql:/var/lib/mysql",
                    IMAGE,
                    "--character-set-server=utf8mb4",
                    "--collation-server=utf8mb4_unicode_ci",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        finally:
            os.unlink(filename)
    for _ in range(45):
        probe = subprocess.run(
            [
                "docker",
                "exec",
                CONTAINER,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -Nse "SELECT 1"',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "1":
            database_name = url.path.lstrip("/")
            username = unquote(url.username or "")
            if not re.fullmatch(r"[A-Za-z0-9_]+", database_name) or not re.fullmatch(
                r"[A-Za-z0-9_]+", username
            ):
                raise SystemExit(
                    "Local database and user names must contain only letters, digits and underscores."
                )
            sql = (
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; "
                f"GRANT ALL ON `{database_name}`.* TO '{username}'@'%'; "
                f"GRANT ALL ON `test_{database_name}`.* TO '{username}'@'%';"
            )
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    CONTAINER,
                    "sh",
                    "-c",
                    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot',
                ],
                input=sql,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            if (ROOT / ".university-setup" / "database.sql").exists():
                restore_database(database_name, if_empty=True)
            print(
                "MySQL is responding to SQL queries; local development and test access prepared."
            )
            return
        time.sleep(1)
    raise SystemExit(
        "MySQL did not become ready. Inspect docker logs university-hr-mysql."
    )


def backup():
    values = read_env()
    database_name = urlsplit(values["DATABASE_URL"]).path.lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise SystemExit("Invalid local database name.")
    target = ROOT / ".university-setup" / "database.sql"
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".sql.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        result = subprocess.run(
            [
                "docker",
                "exec",
                CONTAINER,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --no-tablespaces --set-gtid-purged=OFF "$1"',
                "sh",
                database_name,
            ],
            stdout=stream,
        )
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise SystemExit("Backup failed; previous backup was preserved.")
    temporary.replace(target)
    print(
        "Development database backed up to ignored, private .university-setup/database.sql."
    )


def restore_database(database_name=None, *, if_empty=False):
    values = read_env()
    url = urlsplit(values["DATABASE_URL"])
    database_name = database_name or url.path.lstrip("/")
    username = unquote(url.username or "")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", database_name) or not re.fullmatch(
        r"[A-Za-z0-9_]{1,32}", username
    ):
        raise SystemExit("Invalid local database or user name.")
    source = ROOT / ".university-setup" / "database.sql"
    if not source.is_file():
        raise SystemExit(
            "No development snapshot exists. Run the backup command first."
        )
    command = [
        "docker",
        "exec",
        "-i",
        CONTAINER,
        "sh",
        "-c",
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -N "$@"',
        'sh',
    ]
    count = subprocess.run(
        command,
        input=f"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='{database_name}';",
        capture_output=True,
        text=True,
        check=True,
    )
    if int(count.stdout.strip()):
        if if_empty:
            return
        raise SystemExit(
            "Refusing to restore into a nonempty database. Existing data was preserved."
        )
    sql = f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL ON `{database_name}`.* TO '{username}'@'%';"
    subprocess.run(command, input=sql, text=True, check=True)
    with source.open("rb") as stream:
        subprocess.run(command + [database_name], stdin=stream, check=True)
    print("Development snapshot restored into an empty local database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "db", "backup", "restore"])
    parser.add_argument(
        "--database", help="Empty target database for snapshot restoration only."
    )
    args = parser.parse_args()
    if args.action == "init":
        initialize()
    elif args.action == "db":
        database()
    elif args.action == "backup":
        backup()
    else:
        restore_database(args.database)
