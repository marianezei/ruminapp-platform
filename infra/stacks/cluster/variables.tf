variable "cluster_name" {
  type    = string
  default = "ruminapp"
}

variable "node_image" {
  type    = string
  default = "kindest/node:v1.36.4"
}

variable "worker_count" {
  type    = number
  default = 2
}

variable "ingress_http_port" {
  type    = number
  default = 8080
}

variable "registry_port" {
  type    = number
  default = 5001
}

variable "data_dir" {
  description = "Where the kubeconfig and the registry config are written."
  type        = string
  default     = "../../../.data"
}
