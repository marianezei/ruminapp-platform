# Migrations and seed data run once per image version, before the web rollout.
resource "kubernetes_job_v1" "migrate" {
  metadata {
    name      = "migrate-${local.source_hash["web"]}"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels = {
      "app.kubernetes.io/name"    = "migrate"
      "app.kubernetes.io/part-of" = "ruminapp"
    }
  }

  wait_for_completion = true

  timeouts {
    create = "10m"
    update = "10m"
  }

  spec {
    backoff_limit = 6

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name"    = "migrate"
          "app.kubernetes.io/part-of" = "ruminapp"
        }
      }

      spec {
        restart_policy                  = "OnFailure"
        automount_service_account_token = false

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name    = "migrate"
          image   = local.images["web"]
          command = ["sh", "-c", "python manage.py migrate --noinput && python manage.py preparar"]

          dynamic "env" {
            for_each = merge(local.database_env, { METRICS_PORT = "0", RUMINAPP_DEBUG = "0" })
            content {
              name  = env.key
              value = env.value
            }
          }

          dynamic "env" {
            for_each = merge(local.web_secret_env, {
              RUMINAPP_ADMIN_USUARIO   = { secret = kubernetes_secret_v1.app.metadata[0].name, key = "admin-user" }
              RUMINAPP_ADMIN_SENHA     = { secret = kubernetes_secret_v1.app.metadata[0].name, key = "admin-password" }
              RUMINAPP_LOADGEN_USUARIO = { secret = kubernetes_secret_v1.app.metadata[0].name, key = "loadgen-user" }
              RUMINAPP_LOADGEN_SENHA   = { secret = kubernetes_secret_v1.app.metadata[0].name, key = "loadgen-password" }
            })
            content {
              name = env.key
              value_from {
                secret_key_ref {
                  name = env.value.secret
                  key  = env.value.key
                }
              }
            }
          }

          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { memory = "384Mi" }
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
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }
  }

  depends_on = [
    kubernetes_stateful_set_v1.postgres,
    kubernetes_network_policy_v1.postgres,
    kubernetes_network_policy_v1.migrate,
    kubernetes_network_policy_v1.dns,
  ]
}
