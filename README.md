# olist-semantic-agent

Ask business questions in plain language and get answers computed from
governed metric definitions instead of LLM-written SQL.

**Stack:** Snowflake, dbt, MetricFlow (dbt Semantic Layer), MCP, Claude

> Work in progress. Architecture, live demo link and evaluation results follow.

## Phase 1: raw data in Snowflake

Olist Brazilian e-commerce data (9 tables, about 1.55M rows) loaded into
`RAW.OLIST` with role-based access and key-pair service users.

| Role | Can do | Used by |
|---|---|---|
| `LOADER` | Create and load tables in `RAW.OLIST` | `LOADER_SVC` |
| `TRANSFORMER` | Read `RAW`, build `ANALYTICS` | `DBT_SVC` |
| `REPORTER` | Read `ANALYTICS` only | `MCP_SVC` |

Each role has its own X-Small warehouse (60 s auto-suspend), all under one
resource monitor. Raw tables are all `VARCHAR` plus load metadata; typing
happens in dbt.

### Run it

1. Run `snowflake/00_account_setup.sql` in a Snowsight worksheet as your admin user.
2. `./scripts/generate_keys.sh`, then paste the printed `ALTER USER` lines into Snowsight.
3. Copy `config.toml.example` to `~/.snowflake/config.toml`, fill in account and key paths, `chmod 0600` it.
4. `./scripts/download_olist.sh`
5. `./scripts/upload_to_stage.sh` (creates tables, uploads, loads, verifies)

Every status in the first result of `03_verify.sql` should read `OK`.
