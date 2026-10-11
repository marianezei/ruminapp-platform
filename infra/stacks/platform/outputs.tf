output "urls" {
  value = merge(module.observability.urls, { ruminapp = module.ruminapp.url })
}

output "ruminapp_admin_user" {
  value = module.ruminapp.admin_user
}

output "ruminapp_admin_password" {
  value     = module.ruminapp.admin_password
  sensitive = true
}

output "grafana_admin_password" {
  value     = module.observability.grafana_admin_password
  sensitive = true
}

output "images" {
  value = module.ruminapp.images
}
