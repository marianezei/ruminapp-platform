output "name" {
  value = var.name
}

output "service_name" {
  value = kubernetes_service_v1.this.metadata[0].name
}

output "selector" {
  value = local.selector
}

output "port" {
  value = var.port
}
