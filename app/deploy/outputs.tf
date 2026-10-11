output "namespace" {
  value = kubernetes_namespace_v1.this.metadata[0].name
}

output "url" {
  value = "http://${local.public_host}${local.port_suffix}"
}

output "admin_user" {
  value = "admin"
}

output "admin_password" {
  value     = random_password.admin.result
  sensitive = true
}

output "images" {
  value = local.images
}
