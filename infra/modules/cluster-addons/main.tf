resource "kubernetes_namespace_v1" "ingress" {
  metadata {
    name = "ingress"
    labels = {
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
}

resource "helm_release" "traefik" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "traefik"
  namespace  = kubernetes_namespace_v1.ingress.metadata[0].name
  repository = "https://traefik.github.io/charts"
  chart      = "traefik"
  version    = var.chart_versions.traefik
  wait       = true
  timeout    = 600

  values = [yamlencode({
    deployment = {
      replicas = var.ingress_replicas
      podAnnotations = {
        "prometheus.io/scrape" = "true"
        "prometheus.io/port"   = "9100"
      }
    }
    podDisruptionBudget = { enabled = true, maxUnavailable = 1 }
    ingressClass        = { enabled = true, isDefaultClass = true }
    providers = {
      kubernetesIngress = { enabled = true, publishedService = { enabled = false } }
      kubernetesCRD     = { enabled = false }
    }
    ports = {
      web       = { nodePort = var.ingress_node_port }
      websecure = { expose = { default = false } }
    }
    service   = { spec = { type = "NodePort" } }
    log       = { format = "json" }
    accessLog = { enabled = true, format = "json" }
    global    = { checkNewVersion = false, sendAnonymousUsage = false }
    resources = {
      requests = { cpu = "50m", memory = "64Mi" }
      limits   = { cpu = "500m", memory = "192Mi" }
    }
    topologySpreadConstraints = [{
      maxSkew           = 1
      topologyKey       = "kubernetes.io/hostname"
      whenUnsatisfiable = "ScheduleAnyway"
      labelSelector     = { matchLabels = { "app.kubernetes.io/name" = "traefik" } }
    }]
    }), var.otlp_http_endpoint == "" ? "" : yamlencode({
    tracing = {
      serviceName = "traefik"
      otlp = {
        enabled = true
        http    = { enabled = true, endpoint = "${var.otlp_http_endpoint}/v1/traces" }
      }
    }
  })]
}

resource "helm_release" "metrics_server" {
  upgrade_install = true
  atomic          = true
  max_history     = 5

  name       = "metrics-server"
  namespace  = "kube-system"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = var.chart_versions.metrics_server
  wait       = true

  values = [yamlencode({
    # kind kubelets serve self-signed certificates.
    args = ["--kubelet-insecure-tls"]
    resources = {
      requests = { cpu = "50m", memory = "64Mi" }
      limits   = { memory = "128Mi" }
    }
  })]
}

resource "kubernetes_storage_class_v1" "retain" {
  metadata {
    name = "standard-retain"
  }
  storage_provisioner    = "rancher.io/local-path"
  reclaim_policy         = "Retain"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = false
}

resource "kubernetes_priority_class_v1" "platform" {
  metadata {
    name = "platform-critical"
  }
  value          = 100000
  description    = "Platform components (observability, ingress, database)."
  global_default = false
}
