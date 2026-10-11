variable "name" {
  type = string
}

variable "namespace" {
  type = string
}

variable "part_of" {
  type = string
}

variable "image" {
  type = string
}

variable "version_label" {
  type = string
}

variable "port" {
  type    = number
  default = 8080
}

variable "metrics_port" {
  type    = number
  default = 9464
}

variable "env" {
  type    = map(string)
  default = {}
}

variable "secret_env" {
  description = "Environment variables read from secrets: name => { secret, key }."
  type = map(object({
    secret = string
    key    = string
  }))
  default = {}
}

variable "resources" {
  type = object({
    requests = map(string)
    limits   = map(string)
  })
}

variable "autoscaling" {
  type = object({
    min_replicas      = number
    max_replicas      = number
    cpu_target        = number
    scale_down_window = optional(number, 120)
  })
}

variable "probes" {
  type = object({
    liveness_path  = string
    readiness_path = string
  })
  default = {
    liveness_path  = "/healthz"
    readiness_path = "/readyz"
  }
}

variable "labels" {
  description = "Labels extras nos pods (usados pelas NetworkPolicies)."
  type        = map(string)
  default     = {}
}
