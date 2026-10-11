resource "kubernetes_cluster_role_binding_v1" "platform_admins" {
  metadata {
    name = "platform-admins"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }
  subject {
    kind      = "Group"
    name      = var.groups.platform_admins
    api_group = "rbac.authorization.k8s.io"
  }
}

# Read access to the whole cluster without secrets (the built-in "view" role already excludes them).
resource "kubernetes_cluster_role_v1" "cluster_reader" {
  metadata {
    name = "cluster-reader"
  }
  aggregation_rule {
    cluster_role_selectors {
      match_labels = { "rbac.authorization.k8s.io/aggregate-to-view" = "true" }
    }
    cluster_role_selectors {
      match_labels = { "ruminapp.dev/aggregate-to-cluster-reader" = "true" }
    }
  }
}

resource "kubernetes_cluster_role_v1" "cluster_scoped_reader" {
  metadata {
    name   = "cluster-scoped-reader"
    labels = { "ruminapp.dev/aggregate-to-cluster-reader" = "true" }
  }
  rule {
    api_groups = [""]
    resources  = ["nodes", "persistentvolumes", "namespaces"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["storage.k8s.io"]
    resources  = ["storageclasses"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["metrics.k8s.io"]
    resources  = ["nodes", "pods"]
    verbs      = ["get", "list"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "auditors" {
  metadata {
    name = "auditors"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.cluster_reader.metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = var.groups.auditors
    api_group = "rbac.authorization.k8s.io"
  }
}

# Developers operate the app (logs, port-forward, restarts, scaling)
# but cannot read secrets or change RBAC and network policies.
resource "kubernetes_role_v1" "developer" {
  metadata {
    name      = "developer"
    namespace = var.app_namespace
  }
  rule {
    api_groups = ["", "apps", "batch", "autoscaling", "policy", "networking.k8s.io"]
    resources = [
      "pods", "services", "endpoints", "configmaps", "events", "persistentvolumeclaims",
      "deployments", "replicasets", "statefulsets", "jobs", "cronjobs",
      "horizontalpodautoscalers", "poddisruptionbudgets", "ingresses", "networkpolicies",
    ]
    verbs = ["get", "list", "watch"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods/log", "pods/portforward"]
    verbs      = ["get", "create"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["delete"]
  }
  rule {
    api_groups = ["apps"]
    resources  = ["deployments", "deployments/scale"]
    verbs      = ["patch", "update"]
  }
}

resource "kubernetes_role_binding_v1" "developers" {
  metadata {
    name      = "developers"
    namespace = var.app_namespace
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.developer.metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = var.groups.developers
    api_group = "rbac.authorization.k8s.io"
  }
}

resource "kubernetes_role_binding_v1" "developers_observability" {
  metadata {
    name      = "developers-view"
    namespace = var.observability_namespace
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "view"
  }
  subject {
    kind      = "Group"
    name      = var.groups.developers
    api_group = "rbac.authorization.k8s.io"
  }
}
