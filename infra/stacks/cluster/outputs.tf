output "cluster_name" {
  value = module.cluster.name
}

output "endpoint" {
  value = module.cluster.endpoint
}

output "cluster_ca_certificate" {
  value     = module.cluster.cluster_ca_certificate
  sensitive = true
}

output "client_certificate" {
  value     = module.cluster.client_certificate
  sensitive = true
}

output "client_key" {
  value     = module.cluster.client_key
  sensitive = true
}

output "kubeconfig_path" {
  value = module.cluster.kubeconfig_path
}

output "registry" {
  value = module.cluster.registry
}

output "ingress_http_port" {
  value = var.ingress_http_port
}
