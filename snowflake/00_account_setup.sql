-- =====================================================================
-- 00_account_setup.sql
-- Run once in a Snowsight worksheet as your trial admin user.
-- Creates roles, warehouses, databases, service users, grants and a
-- resource monitor. Safe to re-run.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Roles (functional roles, rolled up to SYSADMIN)
-- ---------------------------------------------------------------------
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS LOADER      COMMENT = 'Loads raw files into RAW';
CREATE ROLE IF NOT EXISTS TRANSFORMER COMMENT = 'dbt: reads RAW, builds ANALYTICS';
CREATE ROLE IF NOT EXISTS REPORTER    COMMENT = 'Read-only on ANALYTICS for MetricFlow, MCP and the demo app';

GRANT ROLE LOADER      TO ROLE SYSADMIN;
GRANT ROLE TRANSFORMER TO ROLE SYSADMIN;
GRANT ROLE REPORTER    TO ROLE SYSADMIN;

-- Let your own user switch into each role directly
SET my_user = CURRENT_USER();
GRANT ROLE LOADER      TO USER IDENTIFIER($my_user);
GRANT ROLE TRANSFORMER TO USER IDENTIFIER($my_user);
GRANT ROLE REPORTER    TO USER IDENTIFIER($my_user);

-- ---------------------------------------------------------------------
-- 2. Warehouses (one per workload for cost attribution, all X-Small)
-- ---------------------------------------------------------------------
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS LOADING_WH
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;
CREATE WAREHOUSE IF NOT EXISTS TRANSFORMING_WH
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;
CREATE WAREHOUSE IF NOT EXISTS REPORTING_WH
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;

-- ---------------------------------------------------------------------
-- 3. Databases
-- ---------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS RAW       COMMENT = 'Untouched source data';
CREATE SCHEMA   IF NOT EXISTS RAW.OLIST COMMENT = 'Olist Brazilian e-commerce CSVs';
CREATE DATABASE IF NOT EXISTS ANALYTICS COMMENT = 'dbt-managed models';

-- ---------------------------------------------------------------------
-- 4. Grants
-- ---------------------------------------------------------------------
USE ROLE SECURITYADMIN;

-- Warehouses
GRANT USAGE, OPERATE ON WAREHOUSE LOADING_WH      TO ROLE LOADER;
GRANT USAGE, OPERATE ON WAREHOUSE TRANSFORMING_WH TO ROLE TRANSFORMER;
GRANT USAGE, OPERATE ON WAREHOUSE REPORTING_WH    TO ROLE REPORTER;

-- LOADER: creates and owns objects in RAW.OLIST
GRANT USAGE ON DATABASE RAW       TO ROLE LOADER;
GRANT USAGE ON SCHEMA   RAW.OLIST TO ROLE LOADER;
GRANT CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA RAW.OLIST TO ROLE LOADER;

-- TRANSFORMER: reads RAW, owns everything it builds in ANALYTICS
GRANT USAGE ON DATABASE RAW       TO ROLE TRANSFORMER;
GRANT USAGE ON SCHEMA   RAW.OLIST TO ROLE TRANSFORMER;
GRANT SELECT ON ALL TABLES    IN SCHEMA RAW.OLIST TO ROLE TRANSFORMER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAW.OLIST TO ROLE TRANSFORMER;
GRANT USAGE, CREATE SCHEMA ON DATABASE ANALYTICS TO ROLE TRANSFORMER;

-- REPORTER: read-only on whatever dbt builds
GRANT USAGE  ON DATABASE ANALYTICS                   TO ROLE REPORTER;
GRANT USAGE  ON FUTURE SCHEMAS IN DATABASE ANALYTICS TO ROLE REPORTER;
GRANT SELECT ON FUTURE TABLES  IN DATABASE ANALYTICS TO ROLE REPORTER;
GRANT SELECT ON FUTURE VIEWS   IN DATABASE ANALYTICS TO ROLE REPORTER;

-- ---------------------------------------------------------------------
-- 5. Service users (key-pair auth only, no passwords)
--    Public keys are attached after running scripts/generate_keys.sh
-- ---------------------------------------------------------------------
CREATE USER IF NOT EXISTS LOADER_SVC
  TYPE = SERVICE DEFAULT_ROLE = LOADER DEFAULT_WAREHOUSE = LOADING_WH
  COMMENT = 'CLI uploads and COPY INTO';
CREATE USER IF NOT EXISTS DBT_SVC
  TYPE = SERVICE DEFAULT_ROLE = TRANSFORMER DEFAULT_WAREHOUSE = TRANSFORMING_WH
  COMMENT = 'dbt runs (local and CI)';
CREATE USER IF NOT EXISTS MCP_SVC
  TYPE = SERVICE DEFAULT_ROLE = REPORTER DEFAULT_WAREHOUSE = REPORTING_WH
  COMMENT = 'MetricFlow queries from the MCP server and demo app';

GRANT ROLE LOADER      TO USER LOADER_SVC;
GRANT ROLE TRANSFORMER TO USER DBT_SVC;
GRANT ROLE REPORTER    TO USER MCP_SVC;

-- ---------------------------------------------------------------------
-- 6. Credit guardrail (the demo app will hit REPORTING_WH publicly)
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE RESOURCE MONITOR IF NOT EXISTS OLIST_MONITOR
  WITH CREDIT_QUOTA = 40
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75  PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND
    ON 110 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE LOADING_WH      SET RESOURCE_MONITOR = OLIST_MONITOR;
ALTER WAREHOUSE TRANSFORMING_WH SET RESOURCE_MONITOR = OLIST_MONITOR;
ALTER WAREHOUSE REPORTING_WH    SET RESOURCE_MONITOR = OLIST_MONITOR;

-- Quick check
SHOW WAREHOUSES LIKE '%_WH';
SHOW USERS LIKE '%_SVC';
