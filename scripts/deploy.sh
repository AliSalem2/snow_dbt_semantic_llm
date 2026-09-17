#!/usr/bin/env bash
# Deploy the demo to Cloud Run. Run from the repo root with .env loaded.
#   PROJECT_ID=my-project ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-europe-west3}"
SERVICE="${SERVICE:-olist-metrics}"
: "${SNOWFLAKE_ACCOUNT:?load .env first}"

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --max-instances=1 \
  --concurrency=4 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=120 \
  --set-env-vars "SNOWFLAKE_ACCOUNT=${SNOWFLAKE_ACCOUNT},SNOWFLAKE_MCP_PRIVATE_KEY_PATH=/secrets/snowflake/key.p8" \
  --set-secrets "/secrets/snowflake/key.p8=snowflake-mcp-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,MCP_TOKEN=mcp-token:latest"
