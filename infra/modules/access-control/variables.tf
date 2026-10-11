variable "app_namespace" {
  type = string
}

variable "observability_namespace" {
  type = string
}

variable "groups" {
  description = "Groups (certificate O field or OIDC claim) bound to each role."
  type = object({
    platform_admins = string
    developers      = string
    auditors        = string
  })
  default = {
    platform_admins = "platform-admins"
    developers      = "ruminapp-developers"
    auditors        = "auditors"
  }
}
