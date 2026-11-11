# Throw-away PostgreSQL + pgvector image used ONLY to verify the handbook's SQL claims.
# It is not the reference implementation's image (that is built in M5).
#
# Why built from source: on 2026-11-07 `docker pull pgvector/pgvector:0.8.7-pg17` failed
# repeatedly with a Docker Hub CDN EOF on this machine. pgvector 0.8.7 is the version the
# handbook researched (SRC-001/002). Base image pinned by digest (postgres 16.12, Alpine).
FROM postgres@sha256:97ff59a4e30e08d1c11bdcd9455e7832368c0572b576c9092cde2df4ae5552a3
RUN apk add --no-cache build-base git \
 && git clone --branch v0.8.7 --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
 && cd /tmp/pgvector && make with_llvm=no && make with_llvm=no install \
 && apk del build-base git && rm -rf /tmp/pgvector
