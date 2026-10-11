#!/usr/bin/env bash
# Checks from outside the cluster that the app responds and that metrics, logs and traces arrive.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

require kubectl curl jq
export KUBECONFIG="${DATA_DIR}/kubeconfig"
load_state_credentials

URLS="$(tf platform output -json urls)"
APP="$(jq -r .ruminapp <<<"$URLS")"
GRAFANA="$(jq -r .grafana <<<"$URLS")"
GRAFANA_AUTH="admin:$(tf platform output -raw grafana_admin_password)"
TIMEOUT="${SMOKE_TIMEOUT:-300}"
FAILURES=0

check() {
  local name="$1"; shift
  local deadline=$(( $(date +%s) + TIMEOUT ))
  until "$@" >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      printf '%s FAIL%s %s\n' "$C_RED" "$C_OFF" "$name"
      FAILURES=$((FAILURES + 1))
      return 0
    fi
    sleep 5
  done
  ok "$name"
}

grafana() { curl -sf -u "$GRAFANA_AUTH" "${GRAFANA}$1" "${@:2}"; }

prom_has() {
  grafana /api/datasources/proxy/uid/prometheus/api/v1/query --get --data-urlencode "query=$1" \
    | jq -e '.data.result | length > 0'
}

loki_has() {
  grafana /api/datasources/proxy/uid/loki/loki/api/v1/query_range --get \
    --data-urlencode "query=$1" --data-urlencode "since=10m" --data-urlencode "limit=1" \
    | jq -e '.data.result | length > 0'
}

tempo_has() {
  grafana /api/datasources/proxy/uid/tempo/api/search --get --data-urlencode "q=$1" --data-urlencode "limit=1" \
    | jq -e '.traces | length > 0'
}

datasource_ok() { grafana "/api/datasources/uid/$1/health" | jq -e '.status == "OK"'; }

info "checking the environment (up to ${TIMEOUT}s per item)"

check "app pods ready" kubectl -n ruminapp wait --for=condition=Ready pod -l app.kubernetes.io/part-of=ruminapp,app.kubernetes.io/name!=migrate --timeout=10s
check "observability pods ready" kubectl -n observability wait --for=condition=Ready pod --all --timeout=10s
check "RuminApp answers through the ingress" curl -sf -o /dev/null "${APP}/entrar/"
check "Grafana healthy" grafana /api/health
check "datasource Prometheus" datasource_ok prometheus
check "datasource Loki" datasource_ok loki
check "datasource Tempo" datasource_ok tempo
check "web HTTP metrics" prom_has 'sum(rate(http_server_request_duration_seconds_count{namespace="ruminapp", service="web"}[2m])) > 0'
check "reproducao HTTP metrics" prom_has 'sum(rate(http_server_request_duration_seconds_count{namespace="ruminapp", service="reproducao"}[2m])) > 0'
check "Postgres metrics" prom_has 'pg_up{namespace="ruminapp"} == 1'
check "SLO rules evaluated" prom_has 'service:slo_availability_error_ratio:rate5m{service="web"}'
check "cost rules evaluated" prom_has 'namespace:cost_hourly:sum{namespace="ruminapp"}'
check "Tempo span metrics in Prometheus" prom_has 'traces_spanmetrics_calls_total{service="web"}'
check "Tempo service graph" prom_has 'traces_service_graph_request_total{client="web", server="reproducao"}'
check "app JSON logs in Loki" loki_has '{namespace="ruminapp", app="web", level="info"}'
check "web traces in Tempo" tempo_has '{ resource.service.name = "web" }'
check "trace propagated web -> reproducao" tempo_has '{ resource.service.name = "web" } >> { resource.service.name = "reproducao" }'
check "Watchdog alert firing" prom_has 'ALERTS{alertname="Watchdog", alertstate="firing"}'

if [ "$FAILURES" -gt 0 ]; then
  die "${FAILURES} check(s) failed"
fi
ok "all checks passed"
