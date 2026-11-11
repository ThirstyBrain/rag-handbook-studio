#!/bin/sh
# Runs once, on first initialisation of the data directory, as the bootstrap superuser.
# Creates the application roles and hands the database to the owner role. Passwords come from the
# container environment (docker-compose.yml, sourced from .env); nothing secret is stored in this file.
#   rag_owner   owns objects and runs migrations: NOSUPERUSER NOBYPASSRLS
#   rag_app     what the API uses: NOSUPERUSER NOBYPASSRLS, tenant-scoped data access (grants in migrations)
#   rag_worker  what the background worker uses: NOSUPERUSER NOBYPASSRLS, job queue access only
set -eu
: "${RAG_OWNER_PASSWORD:?RAG_OWNER_PASSWORD must be set}"
: "${RAG_APP_PASSWORD:?RAG_APP_PASSWORD must be set}"
: "${RAG_WORKER_PASSWORD:?RAG_WORKER_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v owner_pw="$RAG_OWNER_PASSWORD" -v app_pw="$RAG_APP_PASSWORD" -v worker_pw="$RAG_WORKER_PASSWORD" \
  -v dbname="$POSTGRES_DB" <<'SQL'
CREATE ROLE rag_owner  LOGIN PASSWORD :'owner_pw'  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE rag_app    LOGIN PASSWORD :'app_pw'    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE rag_worker LOGIN PASSWORD :'worker_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
ALTER DATABASE :"dbname" OWNER TO rag_owner;
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO rag_owner, rag_app, rag_worker;
SQL
