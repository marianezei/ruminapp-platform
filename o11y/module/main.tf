locals {
  port_suffix = var.ingress_port == 80 ? "" : ":${var.ingress_port}"

  prometheus_url  = "http://kps-prometheus.${var.namespace}.svc:9090"
  loki_url        = "http://loki.${var.namespace}.svc:3100"
  tempo_url       = "http://tempo.${var.namespace}.svc:3200"
  tempo_otlp_grpc = "tempo.${var.namespace}.svc:4317"
  smtp_host       = "mailpit.${var.namespace}.svc:1025"
  slack_secret    = "alertmanager-slack"
  slack_enabled   = var.slack_webhook_url != ""

  rules = {
    slo = templatefile("${path.module}/../rules/slo.yaml.tftpl", {
      availability_target = var.slo.availability_target
      latency_target      = var.slo.latency_target
      latency_threshold   = var.slo.latency_threshold
      window              = var.slo.window
      namespaces          = join("|", var.slo_namespaces)
      grafana_url         = "http://grafana.${var.domain}${local.port_suffix}"
    })
    cost = templatefile("${path.module}/../rules/cost.yaml.tftpl", {
      cpu_hourly         = var.pricing.cpu_core_hourly
      memory_gib_hourly  = var.pricing.memory_gib_hourly
      storage_gib_hourly = var.pricing.storage_gib_hourly
    })
    ruminapp = file("${path.module}/../rules/ruminapp.yaml")
  }
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name = var.namespace
    labels = {
      "pod-security.kubernetes.io/enforce" = "baseline"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
}

# node-exporter needs hostNetwork/hostPID, so it lives alone in a privileged namespace.
resource "kubernetes_namespace_v1" "node" {
  metadata {
    name = "${var.namespace}-node"
    labels = {
      "pod-security.kubernetes.io/enforce" = "privileged"
    }
  }
}

resource "random_password" "grafana" {
  length  = 24
  special = false
}

resource "kubernetes_secret_v1" "grafana_admin" {
  metadata {
    name      = "grafana-admin"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    admin-user     = "admin"
    admin-password = random_password.grafana.result
  }
}

resource "kubernetes_secret_v1" "slack" {
  count = local.slack_enabled ? 1 : 0

  metadata {
    name      = local.slack_secret
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    webhook-url = var.slack_webhook_url
  }
}

resource "helm_release" "kube_prometheus_stack" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "kps"
  namespace  = kubernetes_namespace_v1.this.metadata[0].name
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.chart_versions.kube_prometheus_stack
  timeout    = 900
  wait       = true

  values = [
    templatefile("${path.module}/../values/kube-prometheus-stack.yaml.tftpl", {
      cluster_name          = var.cluster_name
      domain                = var.domain
      port_suffix           = local.port_suffix
      ingress_class         = var.ingress_class
      storage_class         = var.storage_class
      priority_class        = var.priority_class
      retention             = var.retention.metrics
      retention_size        = var.retention.metrics_size
      prometheus_storage    = var.storage_size.prometheus
      alertmanager_replicas = var.alertmanager_replicas
      smtp_host             = local.smtp_host
      alert_email           = var.alert_email
      slack_enabled         = local.slack_enabled
      slack_secret          = local.slack_secret
      slack_channel         = var.slack_channel
      grafana_secret        = kubernetes_secret_v1.grafana_admin.metadata[0].name
      loki_url              = local.loki_url
      tempo_url             = local.tempo_url
    }),
    yamlencode({
      additionalPrometheusRulesMap = { for name, body in local.rules : name => yamldecode(body) }
      prometheus-node-exporter     = { namespaceOverride = kubernetes_namespace_v1.node.metadata[0].name }
    }),
  ]

  depends_on = [kubernetes_secret_v1.slack]
}

resource "helm_release" "loki" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "loki"
  namespace  = kubernetes_namespace_v1.this.metadata[0].name
  repository = "https://grafana-community.github.io/helm-charts"
  chart      = "loki"
  version    = var.chart_versions.loki
  timeout    = 600

  values = [templatefile("${path.module}/../values/loki.yaml.tftpl", {
    retention      = var.retention.logs
    storage_class  = var.storage_class
    storage_size   = var.storage_size.loki
    priority_class = var.priority_class
  })]
}

resource "helm_release" "tempo" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "tempo"
  namespace  = kubernetes_namespace_v1.this.metadata[0].name
  repository = "https://grafana-community.github.io/helm-charts"
  chart      = "tempo"
  version    = var.chart_versions.tempo
  timeout    = 600

  values = [templatefile("${path.module}/../values/tempo.yaml.tftpl", {
    retention                   = var.retention.traces
    storage_class               = var.storage_class
    storage_size                = var.storage_size.tempo
    priority_class              = var.priority_class
    prometheus_remote_write_url = "${local.prometheus_url}/api/v1/write"
  })]

  depends_on = [helm_release.kube_prometheus_stack]
}

resource "kubernetes_config_map_v1" "alloy" {
  metadata {
    name      = "alloy-config"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    "config.alloy" = file("${path.module}/../alloy/config.alloy")
  }
}

resource "helm_release" "alloy" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "alloy"
  namespace  = kubernetes_namespace_v1.this.metadata[0].name
  repository = "https://grafana.github.io/helm-charts"
  chart      = "alloy"
  version    = var.chart_versions.alloy
  timeout    = 600

  values = [templatefile("${path.module}/../values/alloy.yaml.tftpl", {
    config_map          = kubernetes_config_map_v1.alloy.metadata[0].name
    priority_class      = var.priority_class
    loki_push_url       = "${local.loki_url}/loki/api/v1/push"
    tempo_otlp_endpoint = local.tempo_otlp_grpc
    json_log_namespaces = join("|", var.json_log_namespaces)
  })]

  depends_on = [helm_release.loki, helm_release.tempo]
}
