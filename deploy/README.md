# deploy/

Kustomize entrypoints:
- `deploy/crds/` installs the CRD(s)
- `deploy/app/` installs the operator namespace + RBAC + Deployment

Notes:
- `deploy/examples/` contains example custom resources and Secret templates.
  These are NOT applied by the kustomizations above; keep cluster-specific
  Secrets and CloudflareDNSRecord objects in your cluster config repo.
