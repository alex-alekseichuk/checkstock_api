# One-shot migration runner: applies all dbmate migrations, then exits.
FROM alpine:3.20

ARG DBMATE_VERSION=2.38.1
ARG TARGETARCH

RUN apk add --no-cache curl \
    && curl -fsSL \
       "https://github.com/amacneil/dbmate/releases/download/v${DBMATE_VERSION}/dbmate-linux-${TARGETARCH}" \
       -o /usr/local/bin/dbmate \
    && chmod +x /usr/local/bin/dbmate

COPY db/migrations /migrations

# dbmate reads the DSN from DATABASE_URL and the migrations dir from
# DBMATE_MIGRATIONS_DIR.
ENV DBMATE_MIGRATIONS_DIR=/migrations

CMD ["dbmate", "up"]
