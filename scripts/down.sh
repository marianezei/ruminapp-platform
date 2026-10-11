#!/usr/bin/env bash
# Removes the platform and the cluster. The state backend stays up (PURGE=1 removes everything).
set -euo pipefail
source "$(dirname "$0")/lib.sh"

require docker terraform
export_docker_host

if [ -f "${DATA_DIR}/state-backend.env" ]; then
  "${ROOT_DIR}/scripts/state-backend.sh" up >/dev/null
  load_state_credentials

  if docker ps --format '{{.Names}}' | grep -q '^ruminapp-control-plane$'; then
    info "terraform destroy: platform (${ENVIRONMENT})"
    tf_init platform
    tf platform destroy -input=false -auto-approve -var-file="$(tf_var_file platform)" || \
      warn "platform destroy failed; removing the cluster anyway"
  fi

  info "terraform destroy: cluster (${ENVIRONMENT})"
  tf_init cluster
  tf cluster destroy -input=false -auto-approve -var-file="$(tf_var_file cluster)"
fi

if [ "${PURGE:-0}" = "1" ]; then
  "${ROOT_DIR}/scripts/state-backend.sh" down
  rm -rf "${DATA_DIR}"
  ok "local state removed"
fi

ok "environment removed"
