# PostgreSQL 16 + pgvector 0.8.7 for the reference implementation.
#
# Built from source on a digest-pinned base because pulling pgvector/pgvector:0.8.7-pg17 failed on a
# Docker Hub CDN error on 2026-11-07 (ADR-001 verification). Same recipe as scripts/verify-sql/Dockerfile.
# Revisit when the official image can be pulled (OI-036): switch to it and re-run the SQL suite.
# Build context: reference-implementation/
FROM postgres@sha256:97ff59a4e30e08d1c11bdcd9455e7832368c0572b576c9092cde2df4ae5552a3
RUN apk add --no-cache build-base git \
 && git clone --branch v0.8.7 --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
 && cd /tmp/pgvector && make with_llvm=no && make with_llvm=no install \
 && apk del build-base git && rm -rf /tmp/pgvector
COPY database/init/ /docker-entrypoint-initdb.d/
# Normalise line endings (files authored on Windows) and make the role bootstrap script executable.
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/*.sh /docker-entrypoint-initdb.d/*.sql \
 && chmod 755 /docker-entrypoint-initdb.d/*.sh
