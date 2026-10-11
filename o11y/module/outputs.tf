output "namespace" {
  value = kubernetes_namespace_v1.this.metadata[0].name
}

output "otlp_http_endpoint" {
  description = "Alloy OTLP/HTTP endpoint where applications send traces."
  value       = "http://alloy.${var.namespace}.svc:4318"
}

output "prometheus_remote_write_url" {
  value = "${local.prometheus_url}/api/v1/write"
}

output "grafana_admin_password" {
  value     = random_password.grafana.result
  sensitive = true
}

output "urls" {
  value = {
    grafana      = "http://grafana.${var.domain}${local.port_suffix}"
    prometheus   = "http://prometheus.${var.domain}${local.port_suffix}"
    alertmanager = "http://alertmanager.${var.domain}${local.port_suffix}"
    mailpit      = "http://mail.${var.domain}${local.port_suffix}"
  }
}
