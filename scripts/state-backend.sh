#!/usr/bin/env bash
# Starts (or stops) the local S3 storage that holds the Terraform state.
# It runs outside the cluster because it has to exist before the first `terraform init`.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

CONTAINER="${STATE_CONTAINER:-ruminapp-tfstate}"
IMAGE="rustfs/rustfs:1.0.1"
PORT="${STATE_PORT:-9900}"
CONSOLE_PORT="${STATE_CONSOLE_PORT:-9901}"
BUCKET="tfstate"
ENV_FILE="${DATA_DIR}/state-backend.env"

up() {
  require docker curl openssl
  export_docker_host
  mkdir -p "${DATA_DIR}/state-backend"

  if [ ! -f "$ENV_FILE" ]; then
    umask 077
    cat >"$ENV_FILE" <<CREDS
STATE_ACCESS_KEY=tf$(openssl rand -hex 8)
STATE_SECRET_KEY=$(openssl rand -hex 24)
STATE_ENDPOINT=http://127.0.0.1:${PORT}
STATE_BUCKET=${BUCKET}
CREDS
  fi
  # shellcheck disable=SC1090
  source "$ENV_FILE"

  if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    info "starting state backend (${IMAGE}) at ${STATE_ENDPOINT}"
    docker run -d --name "$CONTAINER" --restart unless-stopped \
      -p "127.0.0.1:${PORT}:9000" -p "127.0.0.1:${CONSOLE_PORT}:9001" \
      -e RUSTFS_ACCESS_KEY="$STATE_ACCESS_KEY" -e RUSTFS_SECRET_KEY="$STATE_SECRET_KEY" \
      -e RUSTFS_CONSOLE_ENABLE=true \
      -v "${DATA_DIR}/state-backend:/data" \
      "$IMAGE" >/dev/null
  fi

  local s3=(curl -sf -o /dev/null --aws-sigv4 "aws:amz:us-east-1:s3" --user "${STATE_ACCESS_KEY}:${STATE_SECRET_KEY}")
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "${STATE_ENDPOINT}" && break
    sleep 1
  done
  if ! "${s3[@]}" -I "${STATE_ENDPOINT}/${BUCKET}"; then
    "${s3[@]}" -X PUT "${STATE_ENDPOINT}/${BUCKET}" || die "could not create bucket ${BUCKET}"
  fi
  ok "state backend ready: ${STATE_ENDPOINT}/${BUCKET} (console at http://127.0.0.1:${CONSOLE_PORT})"
}

down() {
  export_docker_host
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  ok "state backend stopped (data kept in ${DATA_DIR}/state-backend)"
}

case "${1:-up}" in
  up) up ;;
  down) down ;;
  *) die "usage: $0 [up|down]" ;;
esac
