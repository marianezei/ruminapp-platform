variable "name" {
  description = "kind cluster name."
  type        = string
}

variable "node_image" {
  description = "Node image (sets the Kubernetes version)."
  type        = string
}

variable "worker_count" {
  description = "Number of worker nodes."
  type        = number
  default     = 2

  validation {
    condition     = var.worker_count >= 2
    error_message = "The cluster needs at least 2 workers."
  }
}

variable "pod_subnet" {
  type    = string
  default = "10.244.0.0/16"
}

variable "service_subnet" {
  type    = string
  default = "10.96.0.0/16"
}

variable "ingress_http_port" {
  description = "Host port forwarded to the ingress controller."
  type        = number
  default     = 8080
}

variable "ingress_node_port" {
  description = "NodePort usado pelo ingress controller."
  type        = number
  default     = 30080
}

variable "registry_port" {
  description = "Host port for the local image registry."
  type        = number
  default     = 5001
}

variable "data_dir" {
  description = "Host directory for the kubeconfig and the registry config."
  type        = string
}
