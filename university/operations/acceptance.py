"""Fail-closed release acceptance for Bells University; never invent sign-off."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

INSTITUTION = "Bells University of Technology"
MODULES = (
    "staff",
    "recruitment",
    "onboarding",
    "leave",
    "attendance",
    "payroll",
    "promotions",
    "performance",
    "offboarding",
    "documents",
    "reports",
    "assets",
    "helpdesk",
    "projects",
    "meetings",
)
OPERATIONS = (
    "security_review",
    "backup_restore",
    "load_test",
    "disaster_recovery",
    "data_protection",
)


def acceptance_errors(path, revision):
    errors = []
    path = Path(path)
    try:
        manifest = json.loads(path.read_text())
    except (OSError, ValueError):
        return ["Acceptance manifest is missing or invalid."]
    if not isinstance(manifest, dict):
        return ["Acceptance manifest must be an object."]
    if (
        manifest.get("schema_version") != 1
        or manifest.get("institution") != INSTITUTION
    ):
        errors.append(
            "Acceptance must name Bells University of Technology and schema version 1."
        )
    if (
        not re.fullmatch(r"[0-9a-f]{40}", revision or "")
        or manifest.get("source_revision") != revision
    ):
        errors.append("Acceptance must match the exact source commit of this release.")
    if (
        not isinstance(manifest.get("target_staff_count"), int)
        or manifest["target_staff_count"] < 10000
    ):
        errors.append("Acceptance must cover at least 10,000 staff records.")
    reviewer = manifest.get("approved_by") or {}
    if not isinstance(reviewer, dict) or any(
        not isinstance(reviewer.get(k), str)
        or not reviewer[k].strip()
        or reviewer[k].lower() in {"pending", "example", "todo"}
        for k in ("name", "role", "email")
    ):
        errors.append(
            "An authorized university reviewer must supply name, role and email."
        )
    if (
        isinstance(reviewer, dict)
        and str(reviewer.get("role", "")).strip().casefold() != "registrar"
    ):
        errors.append("The Registrar must approve the university release.")
    try:
        approved = datetime.fromisoformat(
            str(manifest.get("approved_at", "")).replace("Z", "+00:00")
        )
        if approved.tzinfo is None or approved > datetime.now(timezone.utc):
            raise ValueError()
    except (TypeError, ValueError):
        errors.append(
            "Approval needs a valid, timezone-aware date that is not in the future."
        )
    for group, required in [("modules", MODULES), ("operations", OPERATIONS)]:
        entries = manifest.get(group)
        if not isinstance(entries, dict):
            entries = {}
        for name in required:
            entry = entries.get(name) or {}
            if not isinstance(entry, dict) or entry.get("status") != "accepted":
                errors.append(f"{group}.{name}: university acceptance is pending.")
                continue
            relative = entry.get("evidence", "")
            try:
                evidence = (path.parent / relative).resolve()
                if (
                    not isinstance(relative, str)
                    or Path(relative).is_absolute()
                    or not relative
                    or not evidence.is_relative_to(path.parent.resolve())
                    or not evidence.is_file()
                ):
                    raise ValueError()
                digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
                if (
                    not isinstance(entry.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", ""))
                    or digest != entry["sha256"]
                ):
                    raise ValueError()
            except (OSError, TypeError, ValueError):
                errors.append(
                    f"{group}.{name}: evidence is missing, outside the acceptance directory or has the wrong digest."
                )
    return errors
