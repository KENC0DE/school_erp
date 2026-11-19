-- Runs once when the dev Postgres volume is created.
-- erp_demo is created by POSTGRES_DB; add the control-plane database.
CREATE DATABASE controller OWNER erp;
