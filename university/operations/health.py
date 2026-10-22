import time
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

HEARTBEAT_KEY = "university:scheduler:heartbeat"


def scheduler_heartbeat():
    cache.set(HEARTBEAT_KEY, time.time(), timeout=90)


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError()
        marker = "university:readiness:cache"
        cache.set(marker, "ok", timeout=5)
        if cache.get(marker) != "ok":
            raise RuntimeError()
        heartbeat = cache.get(HEARTBEAT_KEY)
        if (
            not isinstance(heartbeat, (int, float))
            or not 0 <= time.time() - heartbeat < 75
        ):
            raise RuntimeError()
    except Exception:
        # No exception text, service addresses or credentials in a public response.
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
