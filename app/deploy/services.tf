locals {
  port_suffix = var.ingress_port == 80 ? "" : ":${var.ingress_port}"
  public_host = "ruminapp.${var.domain}"

  telemetry_env = {
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otlp_http_endpoint
    OTEL_TRACES_SAMPLER         = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG     = tostring(var.trace_sample_ratio)
    LOG_LEVEL                   = "INFO"
    METRICS_PORT                = "9464"
  }

  database_env = {
    DATABASE_HOST = kubernetes_service_v1.postgres.metadata[0].name
    DATABASE_NAME = "ruminapp"
    DATABASE_USER = "ruminapp"
  }

  web_env = merge(local.telemetry_env, local.database_env, {
    OTEL_SERVICE_NAME  = "web"
    RUMINAPP_DEBUG     = "0"
    RUMINAPP_HOSTS     = join(",", [local.public_host, "web", "web.${var.namespace}.svc", "localhost"])
    RUMINAPP_ORIGENS   = "http://${local.public_host}${local.port_suffix}"
    REPRODUCAO_URL     = "http://reproducao:8080"
    REPRODUCAO_TIMEOUT = "3"
  })

  web_secret_env = {
    RUMINAPP_SECRET_KEY = { secret = kubernetes_secret_v1.app.metadata[0].name, key = "django-secret-key" }
    DATABASE_PASSWORD   = { secret = kubernetes_secret_v1.postgres.metadata[0].name, key = "password" }
  }

  telemetry_labels = { "ruminapp.dev/telemetry" = "true" }
}

module "reproducao" {
  source = "./modules/service"

  name          = "reproducao"
  namespace     = kubernetes_namespace_v1.this.metadata[0].name
  part_of       = "ruminapp"
  image         = local.images["reproducao"]
  version_label = local.source_hash["reproducao"]
  labels        = local.telemetry_labels

  env = merge(local.telemetry_env, {
    OTEL_SERVICE_NAME = "reproducao"
    CHAOS_ERROR_RATE  = tostring(var.chaos.error_rate)
    CHAOS_LATENCY_MS  = tostring(var.chaos.latency_ms)
  })

  resources = {
    requests = { cpu = "100m", memory = "96Mi" }
    limits   = { cpu = "500m", memory = "256Mi" }
  }
  autoscaling = var.autoscaling["reproducao"]

  depends_on = [kubernetes_network_policy_v1.reproducao, kubernetes_network_policy_v1.telemetry]
}

module "web" {
  source = "./modules/service"

  name          = "web"
  namespace     = kubernetes_namespace_v1.this.metadata[0].name
  part_of       = "ruminapp"
  image         = local.images["web"]
  version_label = local.source_hash["web"]
  labels        = local.telemetry_labels
  env           = local.web_env
  secret_env    = local.web_secret_env

  resources = {
    requests = { cpu = "250m", memory = "192Mi" }
    limits   = { cpu = "1", memory = "384Mi" }
  }
  autoscaling = var.autoscaling["web"]

  depends_on = [kubernetes_job_v1.migrate, module.reproducao, kubernetes_network_policy_v1.web]
}

resource "kubernetes_ingress_v1" "web" {
  metadata {
    name      = "web"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    ingress_class_name = var.ingress_class
    rule {
      host = local.public_host
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = module.web.service_name
              port {
                name = "http"
              }
            }
          }
        }
      }
    }
  }
}
