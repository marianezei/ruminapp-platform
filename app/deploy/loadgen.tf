resource "kubernetes_config_map_v1" "loadgen" {
  count = var.loadgen.enabled ? 1 : 0

  metadata {
    name      = "loadgen-script"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    "script.js" = file("${path.module}/../loadgen/script.js")
  }
}

resource "kubernetes_deployment_v1" "loadgen" {
  count = var.loadgen.enabled ? 1 : 0

  depends_on = [module.web]

  metadata {
    name      = "loadgen"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = { "app.kubernetes.io/name" = "loadgen", "app.kubernetes.io/part-of" = "ruminapp" }
  }

  spec {
    replicas = 1
    selector {
      match_labels = { "app.kubernetes.io/name" = "loadgen" }
    }

    template {
      metadata {
        labels = { "app.kubernetes.io/name" = "loadgen", "app.kubernetes.io/part-of" = "ruminapp" }
        annotations = {
          "checksum/script" = sha1(kubernetes_config_map_v1.loadgen[0].data["script.js"])
        }
      }

      spec {
        automount_service_account_token = false

        security_context {
          run_as_non_root = true
          run_as_user     = 12345
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name  = "k6"
          image = "grafana/k6:1.8.1"
          args  = ["run", "--no-usage-report", "-o", "experimental-prometheus-rw", "/scripts/script.js"]

          env {
            name  = "TARGET_URL"
            value = "http://${module.web.service_name}:${module.web.port}"
          }
          env {
            name  = "VUS"
            value = tostring(var.loadgen.vus)
          }
          env {
            name  = "WRITE_RATIO"
            value = tostring(var.loadgen.write_ratio)
          }
          env {
            name  = "K6_PROMETHEUS_RW_SERVER_URL"
            value = var.prometheus_remote_write_url
          }
          env {
            name  = "K6_PROMETHEUS_RW_TREND_STATS"
            value = "p(95),p(99),avg"
          }
          env {
            name = "LOADGEN_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "loadgen-user"
              }
            }
          }
          env {
            name = "LOADGEN_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "loadgen-password"
              }
            }
          }

          resources {
            requests = { cpu = "50m", memory = "64Mi" }
            limits   = { cpu = "500m", memory = "256Mi" }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            run_as_non_root            = true
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "script"
            mount_path = "/scripts"
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "script"
          config_map {
            name = kubernetes_config_map_v1.loadgen[0].metadata[0].name
          }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }
  }
}
