variable "namespace" {
  type    = string
  default = "ruminapp"
}

variable "environment" {
  type = string
}

variable "domain" {
  type = string
}

variable "ingress_port" {
  type = number
}

variable "ingress_class" {
  type = string
}

variable "ingress_namespace" {
  type = string
}

variable "observability_namespace" {
  type = string
}

variable "registry" {
  description = "Registry the images are pushed to and the nodes pull from."
  type        = string
}

variable "otlp_http_endpoint" {
  type = string
}

variable "prometheus_remote_write_url" {
  type = string
}

variable "storage_class" {
  type = string
}

variable "priority_class" {
  type    = string
  default = null
}

variable "autoscaling" {
  type = map(object({
    min_replicas = number
    max_replicas = number
    cpu_target   = number
  }))
  default = {
    web        = { min_replicas = 2, max_replicas = 6, cpu_target = 70 }
    reproducao = { min_replicas = 2, max_replicas = 6, cpu_target = 70 }
  }
}

variable "postgres" {
  type = object({
    image        = string
    storage_size = string
  })
  default = {
    image        = "postgres:17.11-alpine"
    storage_size = "2Gi"
  }
}

variable "loadgen" {
  type = object({
    enabled     = bool
    vus         = number
    write_ratio = number
  })
  default = {
    enabled     = true
    vus         = 4
    write_ratio = 0.05
  }
}

variable "chaos" {
  description = "Faults injected into the reproducao service to exercise alerts and SLOs."
  type = object({
    error_rate = number
    latency_ms = number
  })
  default = {
    error_rate = 0
    latency_ms = 0
  }

  validation {
    condition     = var.chaos.error_rate >= 0 && var.chaos.error_rate <= 1
    error_message = "error_rate must be between 0 and 1."
  }
}

variable "trace_sample_ratio" {
  type    = number
  default = 1
}
