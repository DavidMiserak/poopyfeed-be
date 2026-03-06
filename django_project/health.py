"""Health check endpoints for Kubernetes liveness and readiness probes."""

import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def healthz(_request):
    """Liveness probe — returns 200 if the application process is running.

    Use for Kubernetes livenessProbe. Does not check dependencies
    (database, Redis) so the pod won't restart on transient DB outages.
    """
    return JsonResponse({"status": "ok"})


def readyz(_request):
    """Readiness probe — returns 200 only if all dependencies are reachable.

    Use for Kubernetes readinessProbe. Checks database and Redis
    connectivity. Returns 503 if any dependency is unreachable, which
    tells K8s to stop routing traffic to this pod.
    """
    checks = {}
    healthy = True

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        logger.warning("Readiness check failed: database unreachable")
        checks["database"] = "unavailable"
        healthy = False

    # Redis check
    try:
        from django.core.cache import cache

        cache.set("_health_check", "1", timeout=5)
        if cache.get("_health_check") == "1":
            checks["cache"] = "ok"
        else:
            checks["cache"] = "unavailable"
            healthy = False
    except Exception:
        logger.warning("Readiness check failed: Redis unreachable")
        checks["cache"] = "unavailable"
        healthy = False

    status_code = 200 if healthy else 503
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=status_code,
    )
