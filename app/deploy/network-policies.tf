locals {
  web_selector        = { "app.kubernetes.io/name" = "web" }
  reproducao_selector = { "app.kubernetes.io/name" = "reproducao" }
}

# Deny everything by default; every required flow is allowed explicitly.
resource "kubernetes_network_policy_v1" "default_deny" {
  metadata {
    name      = "default-deny"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}

resource "kubernetes_network_policy_v1" "dns" {
  metadata {
    name      = "allow-dns"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "kube-system" }
        }
        pod_selector {
          match_labels = { "k8s-app" = "kube-dns" }
        }
      }
      ports {
        protocol = "UDP"
        port     = "53"
      }
      ports {
        protocol = "TCP"
        port     = "53"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "telemetry" {
  metadata {
    name      = "allow-telemetry-export"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = local.telemetry_labels
    }
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = var.observability_namespace }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "alloy" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "4318"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "metrics_scrape" {
  metadata {
    name      = "allow-prometheus-scrape"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = var.observability_namespace }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "prometheus" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "9464"
      }
      ports {
        protocol = "TCP"
        port     = "9187"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "web" {
  metadata {
    name      = "web"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = local.web_selector
    }
    policy_types = ["Ingress", "Egress"]

    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = var.ingress_namespace }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "traefik" }
        }
      }
      from {
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "loadgen" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }

    egress {
      to {
        pod_selector {
          match_labels = local.reproducao_selector
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }

    egress {
      to {
        pod_selector {
          match_labels = local.postgres_selector
        }
      }
      ports {
        protocol = "TCP"
        port     = "5432"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "reproducao" {
  metadata {
    name      = "reproducao"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = local.reproducao_selector
    }
    policy_types = ["Ingress"]
    ingress {
      from {
        pod_selector {
          match_labels = local.web_selector
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = local.postgres_selector
    }
    policy_types = ["Ingress"]
    ingress {
      from {
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "web" }
        }
      }
      from {
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "migrate" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "5432"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "migrate" {
  metadata {
    name      = "migrate"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = { "app.kubernetes.io/name" = "migrate" }
    }
    policy_types = ["Egress"]
    egress {
      to {
        pod_selector {
          match_labels = local.postgres_selector
        }
      }
      ports {
        protocol = "TCP"
        port     = "5432"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "loadgen" {
  metadata {
    name      = "loadgen"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = { "app.kubernetes.io/name" = "loadgen" }
    }
    policy_types = ["Egress"]
    egress {
      to {
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "web" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = var.observability_namespace }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = "prometheus" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "9090"
      }
    }
  }
}
