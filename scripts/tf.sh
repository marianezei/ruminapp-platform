#!/usr/bin/env bash
# Runs Terraform on a stack with the environment's backend and tfvars already set.
# Usage: scripts/tf.sh <cluster|platform> <command> [args...]
#   ex.: scripts/tf.sh platform plan
#        ENVIRONMENT=small scripts/tf.sh platform apply -var 'chaos={error_rate=0.2,latency_ms=0}'
set -euo pipefail
source "$(dirname "$0")/lib.sh"

STACK="${1:?missing stack: cluster or platform}"
CMD="${2:?missing terraform command}"
shift 2

require terraform docker
export_docker_host
load_state_credentials
tf_init "$STACK"

case "$CMD" in
  plan | apply | destroy | refresh | import)
    tf "$STACK" "$CMD" -input=false -var-file="$(tf_var_file "$STACK")" "$@"
    ;;
  *)
    tf "$STACK" "$CMD" "$@"
    ;;
esac
