variable "namespace" {
  type    = string
  default = "observability"
}

variable "cluster_name" {
  type = string
}

variable "domain" {
  description = "Base domain for ingresses (localtest.me resolves to 127.0.0.1)."
  type        = string
}

variable "ingress_port" {
  description = "Public ingress port, used to build external URLs."
  type        = number
}

variable "ingress_class" {
  type = string
}

variable "storage_class" {
  type    = string
  default = "standard"
}

variable "priority_class" {
  type    = string
  default = null
}

variable "chart_versions" {
  type = object({
    kube_prometheus_stack = string
    loki                  = string
    tempo                 = string
    alloy                 = string
  })
}

variable "retention" {
  type = object({
    metrics      = string
    metrics_size = string
    logs         = string
    traces       = string
  })
  default = {
    metrics      = "7d"
    metrics_size = "8GB"
    logs         = "168h"
    traces       = "72h"
  }
}

variable "storage_size" {
  type = object({
    prometheus = string
    loki       = string
    tempo      = string
  })
  default = {
    prometheus = "10Gi"
    loki       = "5Gi"
    tempo      = "5Gi"
  }
}

variable "alertmanager_replicas" {
  type    = number
  default = 2
}

variable "alert_email" {
  description = "Alert recipient (delivered to the local Mailpit)."
  type        = string
  default     = "oncall@ruminapp.local"
}

variable "slack_webhook_url" {
  description = "Slack webhook for critical alerts. Empty disables it."
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_channel" {
  type    = string
  default = "#ruminapp-alertas"
}

variable "json_log_namespaces" {
  description = "Namespaces that log JSON; level and trace_id are extracted from them."
  type        = list(string)
  default     = []
}

variable "slo" {
  description = "latency_threshold must match a histogram bucket exactly (e.g. \"0.5\", \"1.0\")."
  type = object({
    availability_target = number
    latency_target      = number
    latency_threshold   = string
    window              = string
  })
  default = {
    availability_target = 0.995
    latency_target      = 0.99
    latency_threshold   = "0.5"
    window              = "7d"
  }

  validation {
    condition     = contains(["0.1", "0.25", "0.5", "1.0", "2.5", "5.0"], var.slo.latency_threshold)
    error_message = "latency_threshold must be one of the histogram buckets: 0.1, 0.25, 0.5, 1.0, 2.5 or 5.0."
  }

  validation {
    condition     = var.slo.availability_target < 1 && var.slo.latency_target < 1
    error_message = "SLO targets must be below 1 (a 100% SLO leaves no error budget)."
  }
}

variable "slo_namespaces" {
  description = "Namespaces whose HTTP services get availability and latency SLOs."
  type        = list(string)
  default     = []
}

variable "pricing" {
  description = "Hourly prices used for cost tracking (OpenCost defaults for clusters without a cloud provider)."
  type = object({
    cpu_core_hourly    = number
    memory_gib_hourly  = number
    storage_gib_hourly = number
  })
  default = {
    cpu_core_hourly    = 0.031611
    memory_gib_hourly  = 0.004237
    storage_gib_hourly = 0.00005479452
  }
}
