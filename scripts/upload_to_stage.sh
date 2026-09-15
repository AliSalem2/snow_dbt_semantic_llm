#!/usr/bin/env bash
# Creates raw objects, uploads data/raw/*.csv to the stage, loads and verifies.
# Needs the Snowflake CLI (pip install snowflake-cli) and the
# "olist_loader" connection from config.toml.example.
set -euo pipefail
cd "$(dirname "$0")/.."

CONN="${SNOWFLAKE_CONNECTION:-olist_loader}"

snow connection test -c "$CONN"
snow sql -c "$CONN" -f snowflake/01_raw_objects.sql
snow sql -c "$CONN" -q "PUT 'file://${PWD}/data/raw/*.csv' @RAW.OLIST.OLIST_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
snow sql -c "$CONN" -f snowflake/02_copy_into.sql
snow sql -c "$CONN" -f snowflake/03_verify.sql
