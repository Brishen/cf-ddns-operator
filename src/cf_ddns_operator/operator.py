from __future__ import annotations

import base64
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import aiohttp
import kopf
from kubernetes_asyncio import client, config


GROUP = "dns.cloudflare.com"
VERSION = "v1alpha1"
PLURAL = "cloudflarednsrecords"


CloudflareRecordType = Literal["A", "AAAA"]


@dataclass(frozen=True)
class SecretRef:
    name: str
    key: str


@dataclass(frozen=True)
class IPConfig:
    url: str = "https://api.ipify.org"
    timeout_seconds: int = 5


@dataclass(frozen=True)
class RecordSpec:
    zone_name: str
    zone_id: str | None
    record_name: str
    record_type: CloudflareRecordType
    proxied: bool
    ttl: int
    ip: IPConfig
    sync_interval_seconds: int
    secret_ref: SecretRef


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fqdn(zone_name: str, record_name: str) -> str:
    if record_name == "@":
        return zone_name.rstrip(".")
    return record_name.rstrip(".")


def _validate_ip(ip_str: str, record_type: CloudflareRecordType) -> str:
    ip_obj = ipaddress.ip_address(ip_str)
    if record_type == "A" and ip_obj.version != 4:
        raise ValueError(f"Expected IPv4 for A record, got: {ip_str}")
    if record_type == "AAAA" and ip_obj.version != 6:
        raise ValueError(f"Expected IPv6 for AAAA record, got: {ip_str}")
    return ip_str


async def _load_kube() -> None:
    # In-cluster first; fall back to local config for dev.
    try:
        config.load_incluster_config()
    except config.ConfigException:
        await config.load_kube_config()


async def _read_secret(namespace: str, ref: SecretRef) -> str:
    api = client.CoreV1Api()
    sec = await api.read_namespaced_secret(name=ref.name, namespace=namespace)
    if not sec.data or ref.key not in sec.data:
        raise KeyError(f"Secret {namespace}/{ref.name} missing key: {ref.key}")
    raw = base64.b64decode(sec.data[ref.key]).decode("utf-8").strip()
    if not raw:
        raise ValueError(f"Secret {namespace}/{ref.name} key {ref.key} is empty")
    return raw


class CloudflareClient:
    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._base = "https://api.cloudflare.com/client/v4"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _req(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Any:
        url = f"{self._base}{path}"
        async with self._session.request(method, url, headers=self._headers, params=params, json=json) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400 or not data.get("success", False):
                raise RuntimeError(f"Cloudflare API error {resp.status} {path}: {data}")
            return data["result"]

    async def resolve_zone_id(self, zone_name: str) -> str:
        res = await self._req("GET", "/zones", params={"name": zone_name, "status": "active"})
        if not res:
            raise RuntimeError(f"No active zone found for name={zone_name}")
        return res[0]["id"]

    async def find_record(self, zone_id: str, record_type: CloudflareRecordType, name: str) -> dict[str, Any] | None:
        res = await self._req(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"type": record_type, "name": name},
        )
        if not res:
            return None
        if len(res) > 1:
            raise RuntimeError(f"Multiple records found for {record_type} {name} in zone {zone_id}; refuse to choose")
        return res[0]

    async def create_record(self, zone_id: str, record_type: CloudflareRecordType, name: str, content: str, ttl: int, proxied: bool) -> dict[str, Any]:
        payload = {"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
        return await self._req("POST", f"/zones/{zone_id}/dns_records", json=payload)

    async def update_record(self, zone_id: str, record_id: str, record_type: CloudflareRecordType, name: str, content: str, ttl: int, proxied: bool) -> dict[str, Any]:
        payload = {"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
        return await self._req("PUT", f"/zones/{zone_id}/dns_records/{record_id}", json=payload)


async def _fetch_public_ip(ip_cfg: IPConfig, record_type: CloudflareRecordType, session: aiohttp.ClientSession) -> str:
    timeout = aiohttp.ClientTimeout(total=ip_cfg.timeout_seconds)
    async with session.get(ip_cfg.url, timeout=timeout) as resp:
        text = (await resp.text()).strip()
        # Support simple JSON like {"ip":"1.2.3.4"} as well as raw text.
        if text.startswith("{") and "ip" in text:
            try:
                data = await resp.json(content_type=None)
                text = str(data.get("ip", "")).strip()
            except Exception:
                pass
        return _validate_ip(text, record_type)


def _parse_spec(spec: dict[str, Any]) -> RecordSpec:
    sr = spec["secretRef"]
    ip = spec.get("ip", {}) or {}
    return RecordSpec(
        zone_name=spec["zoneName"],
        zone_id=spec.get("zoneId"),
        record_name=spec["recordName"],
        record_type=(spec.get("type") or "A"),
        proxied=bool(spec.get("proxied", False)),
        ttl=int(spec.get("ttl", 1)),
        ip=IPConfig(
            url=str(ip.get("url", "https://api.ipify.org")),
            timeout_seconds=int(ip.get("timeoutSeconds", 5)),
        ),
        sync_interval_seconds=int(spec.get("syncIntervalSeconds", 300)),
        secret_ref=SecretRef(name=sr["name"], key=sr["key"]),
    )


async def _reconcile(
    *,
    namespace: str,
    name: str,
    spec_dict: dict[str, Any],
    status: dict[str, Any],
    patch: kopf.Patch,
) -> None:
    spec = _parse_spec(spec_dict)
    fqdn = _fqdn(spec.zone_name, spec.record_name)

    async with aiohttp.ClientSession() as session:
        public_ip = await _fetch_public_ip(spec.ip, spec.record_type, session)

        # If no change, no API call.
        if status.get("currentIP") == public_ip and status.get("zoneId") and status.get("recordId"):
            patch.status["lastSyncTime"] = _now_rfc3339()
            patch.status["message"] = f"No change; {fqdn} already {public_ip}"
            return

        token = await _read_secret(namespace, spec.secret_ref)
        cf = CloudflareClient(token=token, session=session)

        zone_id = spec.zone_id or status.get("zoneId") or await cf.resolve_zone_id(spec.zone_name)

        existing = await cf.find_record(zone_id=zone_id, record_type=spec.record_type, name=fqdn)
        if existing is None:
            created = await cf.create_record(
                zone_id=zone_id,
                record_type=spec.record_type,
                name=fqdn,
                content=public_ip,
                ttl=spec.ttl,
                proxied=spec.proxied,
            )
            patch.status["recordId"] = created["id"]
            patch.status["message"] = f"Created {spec.record_type} {fqdn} -> {public_ip}"
        else:
            rec_id = existing["id"]
            content = existing.get("content")
            if content != public_ip or bool(existing.get("proxied", False)) != spec.proxied or int(existing.get("ttl", spec.ttl)) != spec.ttl:
                updated = await cf.update_record(
                    zone_id=zone_id,
                    record_id=rec_id,
                    record_type=spec.record_type,
                    name=fqdn,
                    content=public_ip,
                    ttl=spec.ttl,
                    proxied=spec.proxied,
                )
                patch.status["recordId"] = updated["id"]
                patch.status["message"] = f"Updated {spec.record_type} {fqdn}: {content} -> {public_ip}"
            else:
                patch.status["recordId"] = rec_id
                patch.status["message"] = f"No change; Cloudflare already has {fqdn} -> {public_ip}"

        patch.status["zoneId"] = zone_id
        patch.status["currentIP"] = public_ip
        patch.status["lastSyncTime"] = _now_rfc3339()


@kopf.on.startup()
async def startup(settings: kopf.OperatorSettings, **_: Any) -> None:
    await _load_kube()
    # Conservative defaults; tune if you have many records.
    settings.execution.max_workers = 10


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
async def on_change(spec: dict[str, Any], status: dict[str, Any], name: str, namespace: str, patch: kopf.Patch, body: dict[str, Any], **_: Any) -> None:
    patch.status["observedGeneration"] = body.get("metadata", {}).get("generation")
    try:
        await _reconcile(namespace=namespace, name=name, spec_dict=spec, status=status, patch=patch)
    except Exception as e:
        # Retry transient failures (network / API / auth issues).
        raise kopf.TemporaryError(str(e), delay=30) from e


@kopf.timer(GROUP, VERSION, PLURAL, interval=60.0, sharp=True)
async def periodic(spec: dict[str, Any], status: dict[str, Any], name: str, namespace: str, patch: kopf.Patch, **_: Any) -> None:
    # Per-resource interval gating (kopf's timer interval is global per kind).
    desired = int((spec or {}).get("syncIntervalSeconds", 300))
    last = status.get("lastSyncTime")
    if last:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age < desired:
                return
        except Exception:
            pass

    try:
        await _reconcile(namespace=namespace, name=name, spec_dict=spec, status=status, patch=patch)
    except Exception as e:
        raise kopf.TemporaryError(str(e), delay=30) from e
