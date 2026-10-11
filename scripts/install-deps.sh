#!/usr/bin/env bash
# Installs what the project needs: Docker, kind, kubectl, Terraform, Helm and a few utilities.
# Supports macOS, Debian/Ubuntu, Amazon Linux 2 and 2023, Fedora and RHEL/Rocky/Alma.
#
# Missing binaries are downloaded from their official release pages at the versions below
# and verified against the published SHA-256. Tools that are already installed are kept.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

KIND_VERSION="${KIND_VERSION:-v0.33.0}"
KUBECTL_VERSION="${KUBECTL_VERSION:-v1.36.4}"
TERRAFORM_VERSION="${TERRAFORM_VERSION:-1.16.5}"
HELM_VERSION="${HELM_VERSION:-v4.3.0}"
BIN_DIR="${BIN_DIR:-/usr/local/bin}"
# SKIP_DOCKER=1 skips the Docker daemon (e.g. when it is managed some other way).

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$(uname -m)" in
  x86_64 | amd64) ARCH=amd64 ;;
  arm64 | aarch64) ARCH=arm64 ;;
  *) die "unsupported architecture: $(uname -m)" ;;
esac

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "root or sudo is required to install packages"
  SUDO="sudo"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi
}

verify() {
  local file="$1" expected="$2"
  [ "$(sha256 "$file")" = "$expected" ] || die "checksum mismatch for $(basename "$file")"
}

install_bin() {
  $SUDO install -m 0755 "$1" "${BIN_DIR}/$2"
  ok "$2 installed at ${BIN_DIR}/$2"
}

# ------------------------------------------------------------------ system packages

detect_distro() {
  if [ "$OS" = "darwin" ]; then echo macos; return; fi
  [ -f /etc/os-release ] || die "cannot identify the Linux distribution"
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID}:${VERSION_ID:-}" in
    amzn:2) echo amzn2 ;;
    amzn:*) echo amzn2023 ;;
    ubuntu:* | debian:* | linuxmint:* | pop:*) echo debian ;;
    fedora:*) echo fedora ;;
    rhel:* | rocky:* | almalinux:* | centos:*) echo rhel ;;
    *)
      case "${ID_LIKE:-}" in
        *debian*) echo debian ;;
        *rhel* | *fedora*) echo rhel ;;
        *) die "unsupported distribution: ${ID}" ;;
      esac
      ;;
  esac
}

install_packages() {
  local distro="$1"
  info "installing base packages (${distro})"
  case "$distro" in
    macos)
      command -v brew >/dev/null 2>&1 || die "install Homebrew first: https://brew.sh"
      brew install jq make git curl openssl unzip >/dev/null
      ;;
    debian)
      $SUDO apt-get update -qq
      $SUDO apt-get install -y -qq curl jq make git openssl unzip ca-certificates >/dev/null
      ;;
    amzn2)
      $SUDO yum install -y -q curl jq make git openssl unzip tar gzip >/dev/null
      ;;
    amzn2023 | fedora | rhel)
      # AL2023 ships curl-minimal, which conflicts with the full curl package.
      command -v curl >/dev/null 2>&1 || $SUDO dnf install -y -q curl
      $SUDO dnf install -y -q jq make git openssl unzip tar gzip >/dev/null
      ;;
  esac
}

install_docker() {
  local distro="$1"
  if command -v docker >/dev/null 2>&1; then
    ok "docker already installed ($(docker --version | cut -d, -f1))"
  else
    info "installing Docker"
    case "$distro" in
      macos)
        # Without Docker Desktop, use Colima (a small VM running the Docker daemon).
        brew install colima docker >/dev/null
        ;;
      debian)
        $SUDO apt-get install -y -qq docker.io >/dev/null
        ;;
      amzn2)
        $SUDO yum install -y -q docker >/dev/null
        ;;
      amzn2023)
        $SUDO dnf install -y -q docker >/dev/null
        ;;
      fedora)
        $SUDO dnf install -y -q moby-engine >/dev/null
        ;;
      rhel)
        $SUDO dnf install -y -q dnf-plugins-core >/dev/null
        local repo=centos
        grep -q '^ID="\?rhel' /etc/os-release && repo=rhel
        $SUDO dnf config-manager --add-repo "https://download.docker.com/linux/${repo}/docker-ce.repo"
        $SUDO dnf install -y -q docker-ce docker-ce-cli containerd.io >/dev/null
        ;;
    esac
  fi

  if [ "$distro" = "macos" ]; then
    if ! docker info >/dev/null 2>&1 && command -v colima >/dev/null 2>&1; then
      info "starting Colima (6 CPUs, 10 GB of memory)"
      colima start --cpu 6 --memory 10 --disk 60
    fi
    return
  fi

  $SUDO systemctl enable --now docker >/dev/null 2>&1 || $SUDO service docker start
  if [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" | grep -qw docker; then
    $SUDO usermod -aG docker "$USER"
    warn "user added to the docker group; open a new session (or run 'newgrp docker') before 'make up'"
  fi
}

# Multi-node kind clusters exceed the default Linux inotify limits.
tune_linux() {
  [ "$OS" = "linux" ] || return 0
  local conf=/etc/sysctl.d/99-kind.conf
  if [ ! -f "$conf" ]; then
    info "raising inotify limits for kind"
    printf 'fs.inotify.max_user_watches = 524288\nfs.inotify.max_user_instances = 512\n' | $SUDO tee "$conf" >/dev/null
    $SUDO sysctl --system >/dev/null
  fi
}

# ------------------------------------------------------------------ binaries

install_kind() {
  if command -v kind >/dev/null 2>&1; then
    ok "kind found: $(kind version | awk '{print $2}')"; return
  fi
  info "downloading kind ${KIND_VERSION}"
  local url="https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${OS}-${ARCH}"
  curl -fsSLo "$TMP/kind" "$url"
  verify "$TMP/kind" "$(curl -fsSL "${url}.sha256sum" | awk '{print $1}')"
  install_bin "$TMP/kind" kind
}

install_kubectl() {
  if command -v kubectl >/dev/null 2>&1; then
    ok "kubectl found: $(kubectl version --client 2>/dev/null | head -1 | awk '{print $3}')"; return
  fi
  info "downloading kubectl ${KUBECTL_VERSION}"
  local url="https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"
  curl -fsSLo "$TMP/kubectl" "$url"
  verify "$TMP/kubectl" "$(curl -fsSL "${url}.sha256")"
  install_bin "$TMP/kubectl" kubectl
}

install_terraform() {
  if command -v terraform >/dev/null 2>&1; then
    local current
    current="$(terraform version | head -1 | sed 's/^Terraform v//')"
    # The S3 backend lock file needs Terraform 1.10 or newer.
    if [ "$(printf '%s\n1.10.0\n' "$current" | sort -V | head -1)" = "1.10.0" ]; then
      ok "terraform found: ${current}"; return
    fi
    warn "terraform ${current} is older than 1.10; installing ${TERRAFORM_VERSION}"
  fi
  info "downloading terraform ${TERRAFORM_VERSION}"
  local base="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}"
  local zip="terraform_${TERRAFORM_VERSION}_${OS}_${ARCH}.zip"
  curl -fsSLo "$TMP/$zip" "$base/$zip"
  verify "$TMP/$zip" "$(curl -fsSL "$base/terraform_${TERRAFORM_VERSION}_SHA256SUMS" | grep " ${zip}$" | awk '{print $1}')"
  unzip -oq "$TMP/$zip" -d "$TMP"
  install_bin "$TMP/terraform" terraform
}

install_helm() {
  if command -v helm >/dev/null 2>&1; then
    ok "helm found: $(helm version --short 2>/dev/null)"; return
  fi
  info "downloading helm ${HELM_VERSION}"
  local tgz="helm-${HELM_VERSION}-${OS}-${ARCH}.tar.gz"
  curl -fsSLo "$TMP/$tgz" "https://get.helm.sh/$tgz"
  verify "$TMP/$tgz" "$(curl -fsSL "https://get.helm.sh/${tgz}.sha256sum" | awk '{print $1}')"
  tar -xzf "$TMP/$tgz" -C "$TMP"
  install_bin "$TMP/${OS}-${ARCH}/helm" helm
}

main() {
  local distro
  distro="$(detect_distro)"
  info "system: ${distro} (${ARCH})"

  install_packages "$distro"
  if [ "${SKIP_DOCKER:-0}" = "1" ]; then
    warn "SKIP_DOCKER=1: Docker installation skipped"
  else
    install_docker "$distro"
    tune_linux
  fi
  $SUDO mkdir -p "$BIN_DIR"
  install_kind
  install_kubectl
  install_terraform
  install_helm

  ok "dependencies ready. Next: make up"
}

main "$@"
