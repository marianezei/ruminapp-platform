# Local mailbox that receives Alertmanager notifications.
resource "kubernetes_deployment_v1" "mailpit" {
  metadata {
    name      = "mailpit"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = { "app.kubernetes.io/name" = "mailpit" }
  }

  spec {
    replicas = 1
    selector {
      match_labels = { "app.kubernetes.io/name" = "mailpit" }
    }

    template {
      metadata {
        labels = { "app.kubernetes.io/name" = "mailpit" }
      }

      spec {
        automount_service_account_token = false

        security_context {
          run_as_non_root = true
          run_as_user     = 1000
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name  = "mailpit"
          image = "axllent/mailpit:v1.31.5"

          port {
            name           = "smtp"
            container_port = 1025
          }
          port {
            name           = "http"
            container_port = 8025
          }

          readiness_probe {
            http_get {
              path = "/readyz"
              port = "http"
            }
          }
          liveness_probe {
            http_get {
              path = "/livez"
              port = "http"
            }
          }

          resources {
            requests = { cpu = "10m", memory = "24Mi" }
            limits   = { memory = "128Mi" }
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
}

resource "kubernetes_service_v1" "mailpit" {
  metadata {
    name      = "mailpit"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    selector = { "app.kubernetes.io/name" = "mailpit" }
    port {
      name        = "smtp"
      port        = 1025
      target_port = "smtp"
    }
    port {
      name        = "http"
      port        = 8025
      target_port = "http"
    }
  }
}

resource "kubernetes_ingress_v1" "mailpit" {
  metadata {
    name      = "mailpit"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    ingress_class_name = var.ingress_class
    rule {
      host = "mail.${var.domain}"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.mailpit.metadata[0].name
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
