locals {
  dashboards = {
    for f in fileset("${path.module}/../dashboards", "**/*.json") :
    trimsuffix(basename(f), ".json") => {
      folder  = dirname(f) == "." ? "RuminApp" : dirname(f)
      content = file("${path.module}/../dashboards/${f}")
    }
  }
}

resource "kubernetes_config_map_v1" "dashboard" {
  for_each = local.dashboards

  metadata {
    name        = "dashboard-${each.key}"
    namespace   = kubernetes_namespace_v1.this.metadata[0].name
    labels      = { grafana_dashboard = "1" }
    annotations = { grafana_folder = each.value.folder }
  }

  data = {
    "${each.key}.json" = each.value.content
  }
}
