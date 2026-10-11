locals {
  sources = {
    web        = abspath("${path.module}/../web")
    reproducao = abspath("${path.module}/../reproducao")
  }

  # The tag changes whenever a source file changes; pods reference the digest.
  source_hash = {
    for name, dir in local.sources : name => substr(sha1(join("", [
      for f in sort(fileset(dir, "**")) : filesha1("${dir}/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.sqlite3$|^staticfiles/|^tests/|\\.pytest_cache)", f))
    ])), 0, 12)
  }
}

resource "docker_image" "this" {
  for_each = local.sources

  name         = "${var.registry}/ruminapp-${each.key}:${local.source_hash[each.key]}"
  keep_locally = true

  build {
    context = each.value
  }

  triggers = {
    source = local.source_hash[each.key]
  }
}

resource "docker_registry_image" "this" {
  for_each = docker_image.this

  name          = each.value.name
  keep_remotely = true

  # The local registry speaks plain HTTP; without the scheme the provider fetches the digest over HTTPS.
  auth_config {
    address  = "http://${var.registry}"
    username = "local"
    password = "local"
  }

  triggers = {
    image = each.value.image_id
  }
}

locals {
  images = {
    for name, img in docker_registry_image.this :
    name => "${img.name}@${img.sha256_digest}"
  }
}
