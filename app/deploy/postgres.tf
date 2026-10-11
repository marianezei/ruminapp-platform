locals {
  postgres_selector = {
    "app.kubernetes.io/name"     = "postgres"
    "app.kubernetes.io/instance" = "postgres"
  }
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.postgres_selector
  }
  spec {
    selector = local.postgres_selector
    port {
      name        = "postgres"
      port        = 5432
      target_port = "postgres"
    }
  }
}

resource "kubernetes_service_v1" "postgres_headless" {
  metadata {
    name      = "postgres-headless"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.postgres_selector
  }
  spec {
    selector   = local.postgres_selector
    cluster_ip = "None"
    port {
      name        = "postgres"
      port        = 5432
      target_port = "postgres"
    }
  }
}

resource "kubernetes_stateful_set_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = merge(local.postgres_selector, { "app.kubernetes.io/part-of" = "ruminapp" })
  }

  wait_for_rollout = true

  depends_on = [kubernetes_network_policy_v1.postgres, kubernetes_network_policy_v1.metrics_scrape]

  spec {
    service_name = kubernetes_service_v1.postgres_headless.metadata[0].name
    replicas     = 1

    selector {
      match_labels = local.postgres_selector
    }

    template {
      metadata {
        labels = merge(local.postgres_selector, { "app.kubernetes.io/part-of" = "ruminapp" })
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "9187"
        }
      }

      spec {
        automount_service_account_token  = false
        priority_class_name              = var.priority_class
        termination_grace_period_seconds = 60

        security_context {
          run_as_non_root = true
          run_as_user     = 70
          run_as_group    = 70
          fs_group        = 70
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name  = "postgres"
          image = var.postgres.image

          port {
            name           = "postgres"
            container_port = 5432
          }

          env {
            name  = "PGDATA"
            value = "/var/lib/postgresql/data/pgdata"
          }
          env {
            name = "POSTGRES_DB"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "database"
              }
            }
          }
          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "username"
              }
            }
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "password"
              }
            }
          }

          readiness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -h 127.0.0.1"]
            }
            period_seconds = 5
          }

          liveness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -h 127.0.0.1"]
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { memory = "512Mi" }
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
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "run"
            mount_path = "/var/run/postgresql"
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        container {
          name  = "exporter"
          image = "prometheuscommunity/postgres-exporter:v0.20.1"

          port {
            name           = "metrics"
            container_port = 9187
          }

          env {
            name  = "DATA_SOURCE_URI"
            value = "127.0.0.1:5432/ruminapp?sslmode=disable"
          }
          env {
            name = "DATA_SOURCE_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "username"
              }
            }
          }
          env {
            name = "DATA_SOURCE_PASS"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "password"
              }
            }
          }

          resources {
            requests = { cpu = "10m", memory = "24Mi" }
            limits   = { memory = "64Mi" }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            run_as_non_root            = true
            run_as_user                = 65534
            capabilities {
              drop = ["ALL"]
            }
          }
        }

        volume {
          name = "run"
          empty_dir {}
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = var.storage_class
        resources {
          requests = { storage = var.postgres.storage_size }
        }
      }
    }
  }
}
