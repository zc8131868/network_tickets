"""
Elasticsearch syslog search service.

Queries the EFK stack (cisco-logs-*, panw-logs-*) and returns normalised
results that are safe and convenient for both Django views and OpenClaw.
"""
from __future__ import annotations

import logging
import re
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

    if query_text:
        must.append({"query_string": {"query": query_text}})

    if vendors:
        filters.append(
            {
                "bool": {
                    "should": [{"term": {"event.module": v}} for v in vendors],
                    "minimum_should_match": 1,
                }
            }
        )

    if devices:
        device_should = []
        for d in devices:
            device_should.append({"term": {"host.name.keyword": d}})
            device_should.append({"term": {"host.hostname.keyword": d}})
            device_should.append({"term": {"observer.hostname.keyword": d}})
            device_should.append({"term": {"hostname.keyword": d}})
            device_should.append({"term": {"host.hostname": d}})
            device_should.append({"term": {"observer.hostname": d}})
            device_should.append({"term": {"hostname": d}})
            device_should.append({"match_phrase": {"host.hostname": d}})
            device_should.append({"match_phrase": {"observer.hostname": d}})
            device_should.append({"match_phrase": {"hostname": d}})
        filters.append(
            {
                "bool": {
                    "should": device_should,
                    "minimum_should_match": 1,
                }
            }
        )

    if ips:
        ip_should = []
        for ip in ips:
            ip_should.append({"term": {"host.ip": ip}})
            ip_should.append({"term": {"observer.ip": ip}})
            ip_should.append({"term": {"source.ip": ip}})
            ip_should.append({"term": {"destination.ip": ip}})
            ip_should.append({"term": {"source.address": ip}})
            ip_should.append({"term": {"destination.address": ip}})
            ip_should.append({"term": {"log.source.address": ip}})
            ip_should.append({"wildcard": {"log.source.address": f"{ip}:*"}})
        filters.append(
            {
                "bool": {
                    "should": ip_should,
                    "minimum_should_match": 1,
                }
            }
        )

    return {
        "size": size,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": [
            "@timestamp",
            "message",
            "event.original",
            "hostname",
            "event.module",
            "event.dataset",
            "event.severity",
            "host.hostname",
            "observer.hostname",
            "host.ip",
            "observer.ip",
            "source.ip",
            "source.address",
            "log.level",
            "log.original",
            "log.source.address",
            "syslog.severity_label",
        ],
        "query": {
            "bool": {
                "filter": filters,
                "must": must,
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
    log_obj = src.get("log", {}) if isinstance(src.get("log"), dict) else {}
    syslog_obj = src.get("syslog", {}) if isinstance(src.get("syslog"), dict) else {}

    # PANW logs commonly use "log.source.address" like "10.254.0.15:54152".
    log_source_address = _deep_get(src, "log.source.address")
    log_source_ip = None
    if isinstance(log_source_address, str) and log_source_address:
        m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})", log_source_address)
        log_source_ip = m.group(1) if m else log_source_address

    message = event.get("original") or src.get("message") or log_obj.get("original")
    device = (
        _deep_get(src, "host.hostname")
        or _deep_get(src, "observer.hostname")
        or src.get("hostname")
    )
    device_ip = (
        _deep_get(src, "host.ip")
        or _deep_get(src, "observer.ip")
        or log_source_ip
    )
    severity = (
        _deep_get(src, "log.level")
        or syslog_obj.get("severity_label")
        or event.get("severity")
    )

    return {
        "timestamp": src.get("@timestamp"),
        "message": message,
        "vendor": event.get("module"),
        "dataset": event.get("dataset"),
        "device": device,
        "device_ip": device_ip,
        "source_ip": _deep_get(src, "source.ip") or _deep_get(src, "source.address"),
        "severity": severity,
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
