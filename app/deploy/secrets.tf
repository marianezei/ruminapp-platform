resource "random_password" "django_secret" {
  length = 50
}

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "random_password" "admin" {
  length  = 20
  special = false
}

resource "random_password" "loadgen" {
  length  = 20
  special = false
}

resource "kubernetes_secret_v1" "app" {
  metadata {
    name      = "ruminapp"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    django-secret-key = random_password.django_secret.result
    admin-user        = "admin"
    admin-password    = random_password.admin.result
    loadgen-user      = "loadgen"
    loadgen-password  = random_password.loadgen.result
  }
}

resource "kubernetes_secret_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  data = {
    database = "ruminapp"
    username = "ruminapp"
    password = random_password.postgres.result
  }
}
