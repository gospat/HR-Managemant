#!/usr/bin/env python3
"""Exercise the local, certificate-verified isolated staging edge."""

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
certificate = ROOT / ".production-staging/tls/fullchain.pem"


def request(path):
    result = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--resolve",
            "hr.test:8443:127.0.0.1",
            "--cacert",
            str(certificate),
            "--max-time",
            "15",
            "--dump-header",
            "-",
            "--output",
            "/dev/null",
            "https://hr.test:8443" + path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    status = int(lines[0].split()[1])
    headers = {
        key.lower(): value.strip()
        for line in lines[1:]
        if ":" in line
        for key, value in [line.split(":", 1)]
    }
    return status, headers


def main():
    status, headers = request("/")
    assert status == 200, f"Frontend returned {status}"
    assert headers.get("strict-transport-security", "").startswith("max-age=31536000")
    assert headers.get("x-content-type-options") == "nosniff"
    assert "x-powered-by" not in headers
    for path in ("/initialize-database/", "/load-demo-database/", "/ready/"):
        assert request(path)[0] == 404, f"Private/setup route exposed: {path}"
    status, headers = request("/university-api/staff/")
    assert status in (401, 403), f"Anonymous staff API returned {status}"
    assert "no-store" in headers.get("cache-control", "")
    assert request("/media/payroll/private.pdf")[0] in (302, 403, 404)
    print(
        json.dumps(
            {
                "tls": "verified",
                "frontend": "ok",
                "security_headers": "ok",
                "setup_routes": "blocked",
                "anonymous_staff_access": "blocked",
            }
        )
    )


if __name__ == "__main__":
    main()
