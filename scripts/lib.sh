#!/usr/bin/env bash
# Shared helpers. Meant to be sourced.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT_DIR}/.data"
ENVIRONMENT="${ENVIRONMENT:-local}"
ENV_DIR="${ROOT_DIR}/infra/environments/${ENVIRONMENT}"

if [ -t 1 ]; then
  C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_OFF=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_OFF=""
fi

info() { printf '%s==>%s %s\n' "$C_BLUE" "$C_OFF" "$*"; }
ok()   { printf '%s ok%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '%s !!%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die()  { printf '%serror:%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }

require() {
  local missing=()
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    die "missing commands: ${missing[*]}. Run 'make deps' (scripts/install-deps.sh)."
  fi
}

# The Terraform providers talk to the daemon directly; the active docker CLI
# context (Docker Desktop, Colima, OrbStack, Rancher) knows where the socket is.
export_docker_host() {
  if [ -z "${DOCKER_HOST:-}" ]; then
    local host
    host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
    [ -n "$host" ] && export DOCKER_HOST="$host"
  fi
  docker info >/dev/null 2>&1 || die "Docker is not responding. Start it and try again."
}

load_state_credentials() {
  local file="${DATA_DIR}/state-backend.env"
  [ -f "$file" ] || die "state backend credentials not found. Run 'make state-backend'."
  # shellcheck disable=SC1090
  source "$file"
  export AWS_ACCESS_KEY_ID="$STATE_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$STATE_SECRET_KEY"
  export TF_VAR_state_endpoint="$STATE_ENDPOINT" TF_VAR_state_bucket="$STATE_BUCKET"
}

tf() {
  local stack="$1"; shift
  terraform -chdir="${ROOT_DIR}/infra/stacks/${stack}" "$@"
}

tf_init() {
  local stack="$1"
  tf "$stack" init -input=false -reconfigure \
    -backend-config="${ROOT_DIR}/infra/environments/backend.hcl" \
    -backend-config="endpoints={s3=\"${STATE_ENDPOINT}\"}" \
    -backend-config="bucket=${STATE_BUCKET}" \
    -backend-config="key=${ENVIRONMENT}/${stack}.tfstate" >/dev/null
}

tf_var_file() {
  local stack="$1"
  echo "${ENV_DIR}/${stack}.tfvars"
}
