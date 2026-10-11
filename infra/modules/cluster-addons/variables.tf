variable "ingress_node_port" {
  description = "Traefik NodePort; must match the kind extraPortMapping."
  type        = number
  default     = 30080
}

variable "ingress_replicas" {
  type    = number
  default = 2
}

variable "otlp_http_endpoint" {
  description = "OTLP/HTTP endpoint for ingress traces. Empty disables tracing."
  type        = string
  default     = ""
}

variable "chart_versions" {
  type = object({
    traefik        = string
    metrics_server = string
  })
}
