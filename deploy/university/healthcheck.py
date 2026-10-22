"""Private HTTP hop; HTTPS terminates at the trusted, isolated edge."""

import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

request = Request(
    "http://127.0.0.1:8000/ready/",
    headers={
        "Host": urlsplit(os.environ["HR_PUBLIC_URL"]).netloc,
        "X-Forwarded-Proto": "https",
    },
)
with urlopen(request, timeout=4) as response:
    if response.status != 200:
        raise SystemExit(1)
