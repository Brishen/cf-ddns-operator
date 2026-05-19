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

1. Build and push the image to your registry:

```bash
make image REGISTRY=myregistry.example.com TAG=latest
```

2. Update `deploy/app/deployment.yaml` with your image, then install the CRD and operator:

```bash
make install-crds
make install
```

3. Create the Cloudflare API token secret (copy and edit the example):

```bash
cp deploy/examples/cloudflare-api-token.secret.example.yaml cloudflare-api-token.secret.yaml
# edit cloudflare-api-token.secret.yaml and replace REPLACE_ME with your token
kubectl apply -f cloudflare-api-token.secret.yaml
```

4. Create one or more DNS records (copy and edit the example):

```bash
cp deploy/examples/cloudflare-dns-record.example.yaml my-record.yaml
# edit my-record.yaml to match your zone and record
kubectl apply -f my-record.yaml
```

Note: The manifests in `deploy/` are scoped to the `networking` namespace. Update `deploy/app/` if you want a different namespace or cluster-wide scope.

## Makefile targets

Run `make` with no arguments to list all targets.

| Target                | Description                                                        |
|-----------------------|--------------------------------------------------------------------|
| `make build`          | Build the container image                                          |
| `make push`           | Push the image to the registry                                     |
| `make image`          | Build and push                                                     |
| `make install-crds`   | Apply the CRD to the cluster                                       |
| `make install`        | Apply the operator (namespace, RBAC, Deployment)                   |
| `make uninstall`      | Remove the operator from the cluster                               |
| `make uninstall-crds` | Remove the CRD (also deletes all `CloudflareDNSRecord` objects)    |
| `make run`            | Run the operator locally against your current kubeconfig           |
| `make lint`           | Run the ruff linter                                                |

### Variables

| Variable         | Default                          | Description                          |
|------------------|----------------------------------|--------------------------------------|
| `REGISTRY`       | `ghcr.io/your-org`               | Registry host and path prefix        |
| `IMAGE`          | `$(REGISTRY)/cf-ddns-operator`   | Full image name                      |
| `TAG`            | `latest`                         | Image tag                            |
| `CONTAINER_TOOL` | `docker`                         | Set to `podman` if preferred         |

Override on the command line: `make image REGISTRY=myregistry.example.com TAG=v1.0.0`

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
- The container runs `kopf` with `--namespace=networking`. Update `deploy/app/deployment.yaml` if you want a different namespace or cluster-wide scope.

## Development
Run locally against your kubeconfig:

```bash
pip install -e .
make run
```
