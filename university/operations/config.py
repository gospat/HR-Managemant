"""Production input validation, independent of Django application startup."""

from pathlib import Path
from urllib.parse import quote, urlsplit
from django.core.exceptions import ImproperlyConfigured
from .acceptance import acceptance_errors


def prepare_environment(values):
    for name in ("SECRET_KEY", "DB_INIT_PASSWORD", "MYSQL_PASSWORD", "REDIS_PASSWORD"):
        filename = values.get(name + "_FILE")
        if filename:
            if values.get(name):
                raise ImproperlyConfigured(
                    f"Use either {name} or its secret file, not both."
                )
            try:
                values[name] = Path(filename).read_text().strip()
            except OSError as exc:
                raise ImproperlyConfigured(
                    f"{name} secret file cannot be read."
                ) from exc
    if not values.get("DATABASE_URL") and all(
        values.get(k)
        for k in ("MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_DATABASE")
    ):
        values["DATABASE_URL"] = (
            f"mysql://{quote(values['MYSQL_USER'], safe='')}:{quote(values['MYSQL_PASSWORD'], safe='')}@{values['MYSQL_HOST']}:{values.get('MYSQL_PORT', '3306')}/{values['MYSQL_DATABASE']}"
        )
    if (
        not values.get("REDIS_URL")
        and values.get("REDIS_PASSWORD")
        and values.get("REDIS_HOST")
    ):
        values["REDIS_URL"] = (
            f"redis://:{quote(values['REDIS_PASSWORD'], safe='')}@{values['REDIS_HOST']}:6379/1"
        )
    return values


def production_errors(values):
    errors = []
    # Malformed IPv6 authorities and non-numeric ports must fail validation,
    # without an exception echoing a credential-bearing URL during startup.
    for key in ("HR_PUBLIC_URL", "DATABASE_URL", "REDIS_URL"):
        try:
            parsed = urlsplit(values.get(key, ""))
            parsed.port
        except ValueError:
            return [f"{key} has an invalid URL authority or port."]
    required = (
        "DEBUG",
        "SECRET_KEY",
        "DB_INIT_PASSWORD",
        "DATABASE_URL",
        "REDIS_URL",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        "HR_PUBLIC_URL",
        "HR_DEPLOYMENT_STAGE",
    )
    for key in required:
        if not values.get(key):
            errors.append(f"{key} must be configured explicitly.")
    if values.get("DEBUG", "").lower() not in {"false", "0"}:
        errors.append("DEBUG must be explicitly false.")
    for key in ("SECRET_KEY", "DB_INIT_PASSWORD"):
        value = values.get(key, "")
        if len(value) < (50 if key == "SECRET_KEY" else 32) or any(
            word in value.lower()
            for word in ("change-me", "django-insecure", "placeholder")
        ):
            errors.append(f"{key} requires a unique production-strength secret.")
    stage = values.get("HR_DEPLOYMENT_STAGE")
    if stage not in {"staging", "production"}:
        errors.append("Stage must be staging or production.")
    public = urlsplit(values.get("HR_PUBLIC_URL", ""))
    if (
        public.scheme != "https"
        or not public.hostname
        or public.username
        or public.password
        or public.path not in {"", "/"}
        or public.query
        or public.fragment
    ):
        errors.append("HR_PUBLIC_URL must be a clean HTTPS origin.")
    hosts = [v.strip() for v in values.get("ALLOWED_HOSTS", "").split(",") if v.strip()]
    if (
        not hosts
        or any("*" in h or h.startswith(".") or "/" in h for h in hosts)
        or public.hostname not in hosts
    ):
        errors.append(
            "Explicit ALLOWED_HOSTS must include the public hostname and contain no wildcards."
        )
    origins = [
        v.strip()
        for v in values.get("CSRF_TRUSTED_ORIGINS", "").split(",")
        if v.strip()
    ]

    def valid_origin(origin):
        try:
            parsed = urlsplit(origin)
            parsed.port
            return (
                parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and "*" not in origin
            )
        except ValueError:
            return False

    if values.get("HR_PUBLIC_URL", "").rstrip("/") not in origins or any(
        not valid_origin(o) for o in origins
    ):
        errors.append(
            "CSRF origins must be explicit HTTPS origins including the public origin."
        )
    database = urlsplit(values.get("DATABASE_URL", ""))
    if (
        database.scheme != "mysql"
        or not database.hostname
        or not database.username
        or database.path in {"", "/"}
        or not database.password
        or database.username == "root"
    ):
        errors.append("A non-root authenticated MySQL connection is required.")
    if database.hostname not in {"mysql", "localhost", "127.0.0.1"} and not values.get(
        "MYSQL_SSL_CA"
    ):
        errors.append("External MySQL requires MYSQL_SSL_CA for verified TLS.")
    redis = urlsplit(values.get("REDIS_URL", ""))
    if (
        redis.scheme not in {"redis", "rediss"}
        or not redis.password
        or not redis.hostname
    ):
        errors.append("An authenticated shared Redis connection is required.")
    if (
        redis.hostname not in {"redis", "localhost", "127.0.0.1"}
        and redis.scheme != "rediss"
    ):
        errors.append(
            "External Redis requires a certificate-verified rediss connection."
        )
    if stage == "production":
        errors.append(
            "Production release remains blocked until safe PDF rendering, "
            "per-document authorization and the university promotion workflow "
            "are implemented and independently verified."
        )
        if public.hostname and (
            public.hostname.endswith((".test", ".example", ".invalid"))
            or public.hostname in {"localhost", "127.0.0.1", "example.com"}
        ):
            errors.append("Production requires the university-owned live hostname.")
        errors.extend(
            acceptance_errors(
                values.get("HR_ACCEPTANCE_FILE", ""),
                values.get("HR_SOURCE_REVISION", ""),
            )
        )
    return errors
