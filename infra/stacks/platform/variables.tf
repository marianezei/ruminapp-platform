variable "environment" {
  type = string
}

variable "state_bucket" {
  type = string
}

variable "state_endpoint" {
  type = string
}

variable "domain" {
  description = "Base domain. localtest.me and all its subdomains resolve to 127.0.0.1."
  type        = string
  default     = "localtest.me"
}

variable "chart_versions" {
  type = object({
    traefik               = string
    metrics_server        = string
    kube_prometheus_stack = string
    loki                  = string
    tempo                 = string
    alloy                 = string
  })
  default = {
    traefik               = "41.7.1"
    metrics_server        = "3.14.0"
    kube_prometheus_stack = "92.3.0"
    loki                  = "18.15.1"
    tempo                 = "3.1.0"
    alloy                 = "1.13.1"
  }
}

variable "ingress_replicas" {
  type    = number
  default = 2
}

variable "observability" {
  type = object({
    alertmanager_replicas = number
    retention = object({
      metrics      = string
      metrics_size = string
      logs         = string
      traces       = string
    })
    storage_size = object({
      prometheus = string
      loki       = string
      tempo      = string
    })
  })
}

variable "slo" {
  type = object({
    availability_target = number
    latency_target      = number
    latency_threshold   = string
    window              = string
  })
}

variable "slack_webhook_url" {
  type      = string
  default   = ""
  sensitive = true
}

variable "autoscaling" {
  type = map(object({
    min_replicas = number
    max_replicas = number
    cpu_target   = number
  }))
}

variable "loadgen" {
  type = object({
    enabled     = bool
    vus         = number
    write_ratio = number
  })
}

variable "chaos" {
  type = object({
    error_rate = number
    latency_ms = number
  })
  default = {
    error_rate = 0
    latency_ms = 0
  }
}

variable "trace_sample_ratio" {
  type    = number
  default = 1
}
