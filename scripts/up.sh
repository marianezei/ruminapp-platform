#!/usr/bin/env bash
# Brings everything up: state backend, kind cluster and platform (observability + app).
set -euo pipefail
source "$(dirname "$0")/lib.sh"

[ -d "$ENV_DIR" ] || die "environment '${ENVIRONMENT}' does not exist in infra/environments"

preflight() {
  require docker terraform kubectl curl openssl jq
  export_docker_host

  local mem_gb
  mem_gb=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 / 1024 ))
  if [ "$mem_gb" -lt 7 ] && [ "$ENVIRONMENT" = "local" ]; then
    warn "Docker has ${mem_gb} GB of memory; 8 GB or more is recommended. Use ENVIRONMENT=small on smaller machines."
  fi

  local port
  port="$(awk -F= '/ingress_http_port/ {gsub(/ /, "", $2); print $2}' "$(tf_var_file cluster)")"
  if ! docker ps --format '{{.Names}}' | grep -q '^ruminapp-control-plane$' \
      && (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
    die "port ${port} is already in use; change ingress_http_port in $(tf_var_file cluster)"
  fi
}

apply_stack() {
  local stack="$1"
  info "terraform apply: ${stack} (${ENVIRONMENT})"
  tf_init "$stack"
  tf "$stack" apply -input=false -auto-approve -var-file="$(tf_var_file "$stack")" "${@:2}"
}

summary() {
  local urls
  urls="$(tf platform output -json urls)"
  cat <<SUMMARY

${C_GREEN}Environment ready.${C_OFF}

  RuminApp      $(jq -r .ruminapp <<<"$urls")   user: admin  password: $(tf platform output -raw ruminapp_admin_password)
  Grafana       $(jq -r .grafana <<<"$urls")   user: admin  password: $(tf platform output -raw grafana_admin_password)
  Prometheus    $(jq -r .prometheus <<<"$urls")
  Alertmanager  $(jq -r .alertmanager <<<"$urls")
  Mailpit       $(jq -r .mailpit <<<"$urls")   (alert e-mails)

  kubectl:   export KUBECONFIG=${DATA_DIR}/kubeconfig
  passwords: make credentials

SUMMARY
}

main() {
  preflight
  "${ROOT_DIR}/scripts/state-backend.sh" up
  load_state_credentials

  apply_stack cluster
  apply_stack platform

  if [ "${SKIP_SMOKE_TEST:-0}" != "1" ]; then
    "${ROOT_DIR}/scripts/smoke-test.sh"
  fi
  summary
}

main "$@"
