#!/bin/bash
# Regenerate server-elasticsearch.pem with SAN so https://172.19.11.14:9200 validates.
# Requires the CA private key. Set CA_KEY env var or pass as first argument.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CA_KEY="${1:-${CA_KEY}}"
if [[ -z "$CA_KEY" || ! -f "$CA_KEY" ]]; then
  echo "Usage: $0 /path/to/ca-key.pem"
  echo "   or: CA_KEY=/path/to/ca-key.pem $0"
  echo ""
  echo "CA private key not found. If you don't have it, use /etc/hosts instead:"
  echo "  172.19.11.14  elasticsearch.qytopensource.com kibana.qytopensource.com"
  exit 1
fi

echo "Using CA key: $CA_KEY"
cp -a server-elasticsearch.pem server-elasticsearch.pem.bak 2>/dev/null || true

openssl req -new -key server-key-elasticsearch.pem -out server-elasticsearch.csr \
  -config elasticsearch-san.cnf -extensions v3_req

openssl x509 -req -in server-elasticsearch.csr \
  -CA ca.cer -CAkey "$CA_KEY" -CAcreateserial \
  -out server-elasticsearch.pem -days 825 \
  -extfile elasticsearch-san.cnf -extensions v3_req

rm -f server-elasticsearch.csr
echo "Done. Restart elasticsearch: docker compose -f docker-compose-tls.yaml restart elasticsearch"
openssl x509 -in server-elasticsearch.pem -noout -text | grep -A2 "Subject Alternative Name"
