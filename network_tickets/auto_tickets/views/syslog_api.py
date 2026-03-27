"""
Internal API for syslog search — called by OpenClaw (exec + curl) or
other internal services.

Authentication: Bearer token (``OPENCLAW_INTERNAL_TOKEN`` in env.conf).
"""
from __future__ import annotations

import json
import logging
import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from auto_tickets.services.elasticsearch_syslog import search_syslogs

logger = logging.getLogger(__name__)

ALLOWED_VENDORS = {"cisco", "panw"}


def _check_bearer_token(request) -> str | None:
    """Return an error message if the token is missing/invalid, else None."""
    expected = settings.OPENCLAW_INTERNAL_TOKEN
    if not expected:
        return None  # token not configured — allow all (dev mode)

    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return "Missing or malformed Authorization header"
    if auth[7:] != expected:
        return "Invalid bearer token"
    return None


@csrf_exempt
@require_POST
def syslog_search_api(request):
    """
    POST /api/openclaw/syslogs/search/

    Body (JSON):
        start       (required)  e.g. "now-2h" or "2026-03-20T00:00:00Z"
        end         (required)  e.g. "now"
        query_text  (optional)  Lucene query string
        devices     (optional)  list of hostnames
        ips         (optional)  list of IP addresses
        vendors     (optional)  list from {"cisco", "panw"}
        size        (optional)  int, default 100, max 200
    """
    auth_err = _check_bearer_token(request)
    if auth_err:
        return JsonResponse({"success": False, "error": auth_err}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)

    start = data.get("start", "").strip()
    end = data.get("end", "").strip()
    if not start or not end:
        return JsonResponse(
            {"success": False, "error": "'start' and 'end' are required"},
            status=400,
        )

    vendors = data.get("vendors")
    if vendors:
        bad = [v for v in vendors if v not in ALLOWED_VENDORS]
        if bad:
            return JsonResponse(
                {"success": False, "error": f"Unknown vendors: {bad}. Allowed: {sorted(ALLOWED_VENDORS)}"},
                status=400,
            )

    t0 = time.monotonic()
    try:
        result = search_syslogs(
            start=start,
            end=end,
            query_text=data.get("query_text", ""),
            devices=data.get("devices"),
            ips=data.get("ips"),
            vendors=vendors,
            size=data.get("size", 100),
        )
    except Exception as e:
        logger.exception("Elasticsearch query failed")
        return JsonResponse({"success": False, "error": str(e)}, status=502)

    elapsed_ms = round((time.monotonic() - t0) * 1000)
    logger.info(
        "syslog_search: total=%s returned=%s elapsed=%dms",
        result["total"],
        len(result["results"]),
        elapsed_ms,
    )

    return JsonResponse({
        "success": True,
        "total": result["total"],
        "count": len(result["results"]),
        "elapsed_ms": elapsed_ms,
        "results": result["results"],
    })
