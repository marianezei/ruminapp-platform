locals {
  registry_name = "${var.name}-registry"
  registry_host = "localhost:${var.registry_port}"
  certs_dir     = abspath("${var.data_dir}/containerd-certs.d")

  registry_mount = {
    host_path      = local.certs_dir
    container_path = "/etc/containerd/certs.d"
  }
}

resource "local_file" "registry_hosts" {
  filename = "${local.certs_dir}/${local.registry_host}/hosts.toml"
  content  = <<-EOT
    [host."http://${local.registry_name}:5000"]
      capabilities = ["pull", "resolve"]
  EOT
}

resource "kind_cluster" "this" {
  name            = var.name
  node_image      = var.node_image
  wait_for_ready  = true
  kubeconfig_path = abspath("${var.data_dir}/kubeconfig")

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    containerd_config_patches = [
      <<-EOT
      [plugins."io.containerd.grpc.v1.cri".registry]
        config_path = "/etc/containerd/certs.d"
      EOT
    ]

    networking {
      pod_subnet     = var.pod_subnet
      service_subnet = var.service_subnet
    }

    node {
      role = "control-plane"

      kubeadm_config_patches = [
        <<-EOT
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
        EOT
      ]

      extra_port_mappings {
        container_port = var.ingress_node_port
        host_port      = var.ingress_http_port
        listen_address = "127.0.0.1"
        protocol       = "TCP"
      }

      dynamic "extra_mounts" {
        for_each = [local.registry_mount]
        content {
          host_path      = extra_mounts.value.host_path
          container_path = extra_mounts.value.container_path
        }
      }
    }

    dynamic "node" {
      for_each = range(var.worker_count)
      content {
        role   = "worker"
        labels = { "topology.kubernetes.io/zone" = "zone-${node.key % 2 == 0 ? "a" : "b"}" }

        dynamic "extra_mounts" {
          for_each = [local.registry_mount]
          content {
            host_path      = extra_mounts.value.host_path
            container_path = extra_mounts.value.container_path
          }
        }
      }
    }
  }

  depends_on = [local_file.registry_hosts]
}

resource "docker_image" "registry" {
  name         = "registry:3.1.2"
  keep_locally = true
}

resource "docker_container" "registry" {
  name    = local.registry_name
  image   = docker_image.registry.image_id
  restart = "always"

  ports {
    internal = 5000
    external = var.registry_port
    ip       = "127.0.0.1"
  }

  networks_advanced {
    name = "kind"
  }

  depends_on = [kind_cluster.this]
}
