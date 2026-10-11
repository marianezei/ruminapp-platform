output "ingress_namespace" {
  value = kubernetes_namespace_v1.ingress.metadata[0].name
}

output "ingress_class" {
  value = "traefik"
}

output "retain_storage_class" {
  value = kubernetes_storage_class_v1.retain.metadata[0].name
}

output "priority_class" {
  value = kubernetes_priority_class_v1.platform.metadata[0].name
}
