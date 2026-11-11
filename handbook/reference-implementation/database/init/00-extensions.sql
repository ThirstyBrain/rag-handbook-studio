-- Runs once, on first initialisation of the data directory (docker-entrypoint-initdb.d).
-- Schema, roles and row-level security are added by migrations (component 2), not here.
CREATE EXTENSION IF NOT EXISTS vector;
