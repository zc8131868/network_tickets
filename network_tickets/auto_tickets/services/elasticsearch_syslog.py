"""
Elasticsearch syslog search service.

Queries the EFK stack (cisco-logs-*, panw-logs-*) and returns normalised
results that are safe and convenient for both Django views and OpenClaw.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

_client: Elasticsearch | None = None


def _get_client() -> Elasticsearch:
    global _client
    if _client is None:
        kwargs: dict[str, Any] = {
            "basic_auth": (settings.ELASTIC_USERNAME, settings.ELASTIC_PASSWORD),
            "request_timeout": 30,
            "retry_on_timeout": True,
            "max_retries": 3,
        }
        if settings.ELASTIC_CA_CERT:
            kwargs["ca_certs"] = settings.ELASTIC_CA_CERT
        _client = Elasticsearch([settings.ELASTIC_URL], **kwargs)
    return _client


def _build_query(
    *,
    start: str,
    end: str,
    query_text: str = "",
    devices: list[str] | None = None,
    ips: list[str] | None = None,
    vendors: list[str] | None = None,
    size: int = 100,
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [
        {"range": {"@timestamp": {"gte": start, "lte": end}}},
    ]
    must: list[dict[str, Any]] = []
    should: list[dict[str, Any]] = []

    if query_text:
        must.append({"query_string": {"query": query_text}})

    if vendors:
        for v in vendors:
            should.append({"term": {"event.module": v}})

    if devices:
        for d in devices:
            should.append({"term": {"host.name.keyword": d}})
            should.append({"term": {"observer.hostname.keyword": d}})

    if ips:
        for ip in ips:
            should.append({"term": {"host.ip": ip}})
            should.append({"term": {"observer.ip": ip}})
            should.append({"term": {"source.ip": ip}})

    return {
        "size": size,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": [
            "@timestamp",
            "message",
            "event.original",
            "event.module",
            "event.dataset",
            "host.hostname",
            "observer.hostname",
            "host.ip",
            "observer.ip",
            "source.ip",
            "source.address",
            "log.level",
        ],
        "query": {
            "bool": {
                "filter": filters,
                "must": must,
                "should": should,
                "minimum_should_match": 1 if should else 0,
            }
        },
    }


def _deep_get(d: dict, dotted_key: str, default=None):
    """Traverse nested dicts using dot-separated keys."""
    keys = dotted_key.split(".")
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default


def _normalise_hit(hit: dict[str, Any]) -> dict[str, Any]:
    src = hit.get("_source", {})
    event = src.get("event", {})
    return {
        "timestamp": src.get("@timestamp"),
        "message": event.get("original") or src.get("message"),
        "vendor": event.get("module"),
        "dataset": event.get("dataset"),
        "device": _deep_get(src, "host.hostname") or _deep_get(src, "observer.hostname"),
        "device_ip": _deep_get(src, "host.ip") or _deep_get(src, "observer.ip"),
        "source_ip": _deep_get(src, "source.ip"),
        "severity": _deep_get(src, "log.level"),
        "index": hit.get("_index"),
        "id": hit.get("_id"),
    }


def search_syslogs(
    *,
    start: str,
    end: str,
    query_text: str = "",
    devices: list[str] | None = None,
    ips: list[str] | None = None,
    vendors: list[str] | None = None,
    size: int = 100,
) -> dict[str, Any]:
    """
    Main entry point.  Returns ``{"total": int, "results": [...]}``.

    Raises ``elasticsearch.ElasticsearchException`` on connection / query
    errors — callers should catch and return an appropriate HTTP response.
    """
    safe_size = min(max(size, 1), settings.ELASTIC_MAX_RESULTS)

    body = _build_query(
        start=start,
        end=end,
        query_text=query_text,
        devices=devices,
        ips=ips,
        vendors=vendors,
        size=safe_size,
    )

    client = _get_client()
    resp = client.search(index=settings.ELASTIC_INDEX_PATTERN, body=body)

    total = resp["hits"]["total"]
    total_value = total["value"] if isinstance(total, dict) else total

    return {
        "total": total_value,
        "results": [_normalise_hit(h) for h in resp["hits"]["hits"]],
    }
