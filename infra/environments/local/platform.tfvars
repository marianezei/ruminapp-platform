environment      = "local"
domain           = "localtest.me"
ingress_replicas = 2

observability = {
  alertmanager_replicas = 2
  retention = {
    metrics      = "7d"
    metrics_size = "8GB"
    logs         = "168h"
    traces       = "72h"
  }
  storage_size = {
    prometheus = "10Gi"
    loki       = "5Gi"
    tempo      = "5Gi"
  }
}

slo = {
  availability_target = 0.995
  latency_target      = 0.99
  latency_threshold   = "0.5"
  window              = "7d"
}

autoscaling = {
  web        = { min_replicas = 2, max_replicas = 6, cpu_target = 70 }
  reproducao = { min_replicas = 2, max_replicas = 6, cpu_target = 70 }
}

loadgen = {
  enabled     = true
  vus         = 4
  write_ratio = 0.05
}
