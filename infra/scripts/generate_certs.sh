#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$(cd "${SCRIPT_DIR}/../nginx/certs" && pwd)"

echo "=== Generating Surakshanet TLS Certificates in ${CERT_DIR} ==="

mkdir -p "${CERT_DIR}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -subj "/C=IN/ST=Delhi/L=New Delhi/O=Surakshanet ITS/OU=Traffic Operations/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:surakshanet.internal,IP:127.0.0.1"

chmod 644 "${CERT_DIR}/fullchain.pem"
chmod 600 "${CERT_DIR}/privkey.pem"

echo "✅ TLS Certificate and Private Key successfully generated:"
echo "   Public Cert: ${CERT_DIR}/fullchain.pem"
echo "   Private Key: ${CERT_DIR}/privkey.pem"
