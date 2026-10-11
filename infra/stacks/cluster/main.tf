module "cluster" {
  source = "../../modules/kind-cluster"

  name              = var.cluster_name
  node_image        = var.node_image
  worker_count      = var.worker_count
  ingress_http_port = var.ingress_http_port
  registry_port     = var.registry_port
  data_dir          = var.data_dir
}
