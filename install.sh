#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Brishen/cf-ddns-operator"
REF="${CF_DDNS_REF:-master}"

if ! command -v kubectl &>/dev/null; then
  echo "Error: kubectl not found in PATH" >&2
  exit 1
fi

echo "Installing cf-ddns-operator (ref: ${REF})..."

echo "  → Applying CRD..."
kubectl apply -k "${REPO}//deploy/crds?ref=${REF}"

echo "  → Applying operator..."
kubectl apply -k "${REPO}//deploy/app?ref=${REF}"

echo ""
echo "cf-ddns-operator installed successfully."
echo ""
echo "Next steps:"
echo ""
echo "  1. Create the Cloudflare API token secret:"
echo "     kubectl create secret generic cloudflare-api-token \\"
echo "       --namespace=networking \\"
echo "       --from-literal=token=<your-cloudflare-api-token>"
echo ""
echo "  2. Create a CloudflareDNSRecord (edit to match your zone and record):"
echo "     kubectl apply -f ${REPO}/raw/master/deploy/examples/cloudflare-dns-record.example.yaml"
echo ""
echo "  Example resource: ${REPO}/blob/master/deploy/examples/cloudflare-dns-record.example.yaml"
