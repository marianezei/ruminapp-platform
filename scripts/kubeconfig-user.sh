#!/usr/bin/env bash
# Issues a kubeconfig for a user in one of the RBAC groups, signed by the cluster CA.
# Usage: scripts/kubeconfig-user.sh <user> <group>
#   ex.: scripts/kubeconfig-user.sh ana ruminapp-developers
set -euo pipefail
source "$(dirname "$0")/lib.sh"

require kubectl openssl
USER_NAME="${1:?missing user name}"
GROUP="${2:?missing group (platform-admins, ruminapp-developers or auditors)}"
export KUBECONFIG="${DATA_DIR}/kubeconfig"
OUT_DIR="${DATA_DIR}/users"
KEY="${OUT_DIR}/${USER_NAME}.key"
CSR_NAME="user-${USER_NAME}"
mkdir -p "$OUT_DIR"

openssl genrsa -out "$KEY" 2048 2>/dev/null
openssl req -new -key "$KEY" -subj "/CN=${USER_NAME}/O=${GROUP}" -out "${OUT_DIR}/${USER_NAME}.csr" 2>/dev/null

kubectl delete csr "$CSR_NAME" --ignore-not-found >/dev/null
kubectl apply -f - >/dev/null <<CSR
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ${CSR_NAME}
spec:
  request: $(base64 <"${OUT_DIR}/${USER_NAME}.csr" | tr -d '\n')
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 86400
  usages: [client auth]
CSR
kubectl certificate approve "$CSR_NAME" >/dev/null
kubectl wait --for=jsonpath='{.status.certificate}' csr/"$CSR_NAME" --timeout=30s >/dev/null 2>&1 || true
kubectl get csr "$CSR_NAME" -o jsonpath='{.status.certificate}' | base64 -d >"${OUT_DIR}/${USER_NAME}.crt"

CONFIG="${OUT_DIR}/${USER_NAME}.kubeconfig"
CLUSTER="$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')"
kubectl config view --minify --raw -o json \
  | jq --arg user "$USER_NAME" \
       --arg crt "$(base64 <"${OUT_DIR}/${USER_NAME}.crt" | tr -d '\n')" \
       --arg key "$(base64 <"$KEY" | tr -d '\n')" \
       --arg cluster "$CLUSTER" \
       '.users = [{name: $user, user: {"client-certificate-data": $crt, "client-key-data": $key}}]
        | .contexts = [{name: $user, context: {cluster: $cluster, user: $user, namespace: "ruminapp"}}]
        | ."current-context" = $user' >"$CONFIG"
chmod 600 "$CONFIG" "$KEY"

ok "kubeconfig written to ${CONFIG} (valid for 24h)"
echo "  try: KUBECONFIG=${CONFIG} kubectl auth can-i --list -n ruminapp"
