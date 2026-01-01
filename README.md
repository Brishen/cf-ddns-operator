# cf-ddns-operator

A Kubernetes operator that keeps Cloudflare DNS A/AAAA records updated with your current public IP. It watches `CloudflareDNSRecord` custom resources and reconciles them on a schedule.

## Features
- Syncs A/AAAA records to the current public IP.
- Supports Cloudflare proxy/TTL settings.
- Per-record sync interval.
- Uses a Kubernetes Secret for the Cloudflare API token.

## Requirements
- Kubernetes cluster with RBAC enabled.
- Cloudflare API token with permission to edit DNS records for the target zone.

## Quick start
1) Create the CRD and RBAC:

```bash
kubectl apply -f deploy/crd.yaml
kubectl apply -f deploy/rbac.yaml
```

2) Create the Cloudflare API token secret:

```bash
kubectl apply -f deploy/cloudflare-api-token.yaml
```

3) Deploy the operator:

```bash
kubectl apply -f deploy/deployment.yaml
```

4) Create one or more records:

```bash
kubectl apply -f deploy/cloudflare-dns-record.yaml
```

Note: The manifests in `deploy/` are templates/examples. Update namespaces, image registry, and record values to match your cluster.

## Custom resource spec
The `CloudflareDNSRecord` resource supports these fields:

- `zoneName` (required): Cloudflare zone name, e.g. `example.com`.
- `zoneId` (optional): Explicit zone ID. If omitted, the operator resolves it via API.
- `recordName` (required): Record name. Use `@` for zone apex.
- `type` (optional): `A` or `AAAA`. Defaults to `A`.
- `proxied` (optional): Cloudflare proxy setting. Defaults to `false`.
- `ttl` (optional): Record TTL in seconds. Use `1` for "auto". Defaults to `1`.
- `ip.url` (optional): URL to fetch the public IP. Defaults to `https://api.ipify.org`.
- `ip.timeoutSeconds` (optional): IP fetch timeout. Defaults to `5`.
- `syncIntervalSeconds` (optional): Per-record reconcile interval. Defaults to `300`.
- `secretRef.name` / `secretRef.key` (required): Secret name/key holding the API token.

Status fields include `currentIP`, `zoneId`, `recordId`, `lastSyncTime`, and `message`.

## Configuration notes
- The deployment and RBAC manifests are scoped to the `networking` namespace.
- The container runs `kopf` with `--namespace=networking`. Update `deploy/deployment.yaml` if you want a different namespace or cluster-wide scope.

## Development
Run locally against your kubeconfig:

```bash
pip install -e .
kopf run -m cf_ddns_operator.operator --verbose
```

## Image
The `Dockerfile` builds a runnable operator image:

```bash
docker build -t cf-ddns-operator:local .
```
