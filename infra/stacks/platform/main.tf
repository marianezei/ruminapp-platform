locals {
  app_namespace           = "ruminapp"
  observability_namespace = "observability"
}

module "addons" {
  source = "../../modules/cluster-addons"

  ingress_replicas   = var.ingress_replicas
  otlp_http_endpoint = "http://alloy.${local.observability_namespace}.svc:4318"
  chart_versions = {
    traefik        = var.chart_versions.traefik
    metrics_server = var.chart_versions.metrics_server
  }
}

module "observability" {
  source = "../../../o11y/module"

  namespace             = local.observability_namespace
  cluster_name          = local.cluster.cluster_name
  domain                = var.domain
  ingress_port          = local.cluster.ingress_http_port
  ingress_class         = module.addons.ingress_class
  priority_class        = module.addons.priority_class
  alertmanager_replicas = var.observability.alertmanager_replicas
  retention             = var.observability.retention
  storage_size          = var.observability.storage_size
  slo                   = var.slo
  slo_namespaces        = [local.app_namespace]
  slack_webhook_url     = var.slack_webhook_url
  json_log_namespaces   = [local.app_namespace, module.addons.ingress_namespace]

  chart_versions = {
    kube_prometheus_stack = var.chart_versions.kube_prometheus_stack
    loki                  = var.chart_versions.loki
    tempo                 = var.chart_versions.tempo
    alloy                 = var.chart_versions.alloy
  }
}

module "ruminapp" {
  source = "../../../app/deploy"

  namespace                   = local.app_namespace
  environment                 = var.environment
  domain                      = var.domain
  ingress_port                = local.cluster.ingress_http_port
  ingress_class               = module.addons.ingress_class
  ingress_namespace           = module.addons.ingress_namespace
  observability_namespace     = module.observability.namespace
  registry                    = local.cluster.registry
  otlp_http_endpoint          = module.observability.otlp_http_endpoint
  prometheus_remote_write_url = module.observability.prometheus_remote_write_url
  storage_class               = module.addons.retain_storage_class
  priority_class              = module.addons.priority_class
  autoscaling                 = var.autoscaling
  loadgen                     = var.loadgen
  chaos                       = var.chaos
  trace_sample_ratio          = var.trace_sample_ratio
}

module "access_control" {
  source = "../../modules/access-control"

  app_namespace           = module.ruminapp.namespace
  observability_namespace = module.observability.namespace
}
