locals {
  selector = {
    "app.kubernetes.io/name"     = var.name
    "app.kubernetes.io/instance" = var.name
  }
  labels = merge(local.selector, var.labels, {
    "app.kubernetes.io/part-of"    = var.part_of
    "app.kubernetes.io/version"    = var.version_label
    "app.kubernetes.io/managed-by" = "terraform"
  })
}

resource "kubernetes_service_account_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.selector
  }
  automount_service_account_token = false
}

resource "kubernetes_deployment_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.labels
  }

  wait_for_rollout = true

  spec {
    replicas               = var.autoscaling.min_replicas
    revision_history_limit = 5

    selector {
      match_labels = local.selector
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    template {
      metadata {
        labels = local.labels
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = tostring(var.metrics_port)
        }
      }

      spec {
        service_account_name             = kubernetes_service_account_v1.this.metadata[0].name
        automount_service_account_token  = false
        termination_grace_period_seconds = 30

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        topology_spread_constraint {
          max_skew           = 1
          topology_key       = "kubernetes.io/hostname"
          when_unsatisfiable = "ScheduleAnyway"
          label_selector {
            match_labels = local.selector
          }
        }

        topology_spread_constraint {
          max_skew           = 1
          topology_key       = "topology.kubernetes.io/zone"
          when_unsatisfiable = "ScheduleAnyway"
          label_selector {
            match_labels = local.selector
          }
        }

        container {
          name  = var.name
          image = var.image

          port {
            name           = "http"
            container_port = var.port
          }
          port {
            name           = "metrics"
            container_port = var.metrics_port
          }

          dynamic "env" {
            for_each = var.env
            content {
              name  = env.key
              value = env.value
            }
          }

          dynamic "env" {
            for_each = var.secret_env
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

          env {
            name = "OTEL_RESOURCE_ATTRIBUTES"
            value = join(",", [
              "service.namespace=${var.part_of}",
              "service.version=${var.version_label}",
              "k8s.namespace.name=${var.namespace}",
            ])
          }

          startup_probe {
            http_get {
              path = var.probes.readiness_path
              port = "http"
              http_header {
                name  = "Host"
                value = "localhost"
              }
            }
            period_seconds    = 2
            failure_threshold = 30
          }

          readiness_probe {
            http_get {
              path = var.probes.readiness_path
              port = "http"
              http_header {
                name  = "Host"
                value = "localhost"
              }
            }
            period_seconds    = 5
            timeout_seconds   = 2
            failure_threshold = 3
          }

          liveness_probe {
            http_get {
              path = var.probes.liveness_path
              port = "http"
              http_header {
                name  = "Host"
                value = "localhost"
              }
            }
            period_seconds    = 10
            timeout_seconds   = 2
            failure_threshold = 3
          }

          # Gives the endpoint time to leave the Service before the process stops.
          lifecycle {
            pre_stop {
              exec {
                command = ["sleep", "5"]
              }
            }
          }

          resources {
            requests = var.resources.requests
            limits   = var.resources.limits
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
          empty_dir {
            medium     = "Memory"
            size_limit = "64Mi"
          }
        }
      }
    }
  }

  # The HPA owns the replica count after creation.
  lifecycle {
    ignore_changes = [spec[0].replicas]
  }
}

resource "kubernetes_service_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.selector
  }
  spec {
    selector = local.selector
    port {
      name        = "http"
      port        = var.port
      target_port = "http"
    }
  }
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
  }

  spec {
    min_replicas = var.autoscaling.min_replicas
    max_replicas = var.autoscaling.max_replicas

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.this.metadata[0].name
    }

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = var.autoscaling.cpu_target
        }
      }
    }

    behavior {
      scale_up {
        stabilization_window_seconds = 30
        select_policy                = "Max"
        policy {
          type           = "Pods"
          value          = 2
          period_seconds = 60
        }
      }
      scale_down {
        stabilization_window_seconds = var.autoscaling.scale_down_window
        select_policy                = "Min"
        policy {
          type           = "Pods"
          value          = 1
          period_seconds = 60
        }
      }
    }
  }
}

resource "kubernetes_pod_disruption_budget_v1" "this" {
  count = var.autoscaling.min_replicas > 1 ? 1 : 0

  metadata {
    name      = var.name
    namespace = var.namespace
  }
  spec {
    max_unavailable = "1"
    selector {
      match_labels = local.selector
    }
  }
}
