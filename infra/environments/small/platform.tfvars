# For machines with ~6 GB of memory available to Docker.
environment      = "small"
domain           = "localtest.me"
ingress_replicas = 1

observability = {
  alertmanager_replicas = 1
  retention = {
    metrics      = "2d"
    metrics_size = "3GB"
    logs         = "48h"
    traces       = "24h"
  }
  storage_size = {
    prometheus = "4Gi"
    loki       = "2Gi"
    tempo      = "2Gi"
  }
}

slo = {
  availability_target = 0.995
  latency_target      = 0.99
  latency_threshold   = "1.0"
  window              = "2d"
}

autoscaling = {
  web        = { min_replicas = 1, max_replicas = 3, cpu_target = 80 }
  reproducao = { min_replicas = 1, max_replicas = 3, cpu_target = 80 }
}

loadgen = {
  enabled     = true
  vus         = 2
  write_ratio = 0.05
}

trace_sample_ratio = 0.5
