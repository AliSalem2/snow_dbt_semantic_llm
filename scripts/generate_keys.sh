#!/usr/bin/env bash
# Generates one RSA key pair per service user in .keys/ (git-ignored)
# and prints the ALTER USER statements to paste into Snowsight.
# Re-running reuses existing keys.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .keys && chmod 700 .keys

echo "-- Paste into a Snowsight worksheet:"
echo "USE ROLE SECURITYADMIN;"
for user in LOADER_SVC DBT_SVC MCP_SVC; do
  lower=$(echo "$user" | tr '[:upper:]' '[:lower:]')
  key=".keys/${lower}_rsa_key.p8"
  pub=".keys/${lower}_rsa_key.pub"
  if [ ! -f "$key" ]; then
    openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -inform PEM -out "$key" -nocrypt
    chmod 600 "$key"
  fi
  openssl rsa -in "$key" -pubout -out "$pub" 2>/dev/null
  body=$(grep -v "PUBLIC KEY" "$pub" | tr -d '\n')
  echo "ALTER USER ${user} SET RSA_PUBLIC_KEY = '${body}';"
done
