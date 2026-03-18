#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ENV="${TARGET_ENV:-prod}"
SKIP_UP=0

usage() {
  cat <<EOF
Usage: $0 [--env prod|test] [--skip-up]

Options:
  --env <prod|test>  Deployment target environment (default: prod)
  --skip-up          Only prepare certificate, skip docker compose up
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --env requires a value (prod|test)." >&2
        exit 1
      fi
      TARGET_ENV="$1"
      ;;
    --env=*)
      TARGET_ENV="${1#*=}"
      ;;
    --skip-up)
      SKIP_UP=1
      ;;
    prod|test)
      TARGET_ENV="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "$TARGET_ENV" != "prod" && "$TARGET_ENV" != "test" ]]; then
  echo "ERROR: invalid --env value: $TARGET_ENV (allowed: prod, test)" >&2
  exit 1
fi

DEFAULT_ENV_FILE="$ROOT_DIR/.env.$TARGET_ENV"
DEFAULT_COMPOSE_FILE="$ROOT_DIR/compose.no-traefik.$TARGET_ENV.yml"
DEFAULT_CERT_DIR="$ROOT_DIR/nginx/certs/$TARGET_ENV"
DEFAULT_DEPLOY_PROJECT_NAME="fsft-$TARGET_ENV"

ENV_FILE="${ENV_FILE:-$DEFAULT_ENV_FILE}"
COMPOSE_FILE="${COMPOSE_FILE:-$DEFAULT_COMPOSE_FILE}"
DEPLOY_PROJECT_NAME="${DEPLOY_PROJECT_NAME:-$DEFAULT_DEPLOY_PROJECT_NAME}"
CERT_DIR="${CERT_DIR:-$DEFAULT_CERT_DIR}"
CERT_FILE="${CERT_FILE:-$CERT_DIR/server.crt}"
KEY_FILE="${KEY_FILE:-$CERT_DIR/server.key}"
CERT_DAYS="${CERT_DAYS:-3650}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required but was not found in PATH." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ ! "$DEPLOY_PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  echo "ERROR: DEPLOY_PROJECT_NAME must match ^[a-z0-9][a-z0-9_-]*$ ; got: $DEPLOY_PROJECT_NAME" >&2
  exit 1
fi

if [[ -z "${CERT_HOSTS:-}" ]]; then
  if [[ -n "${DOMAIN:-}" ]]; then
    CERT_HOSTS="$DOMAIN"
    echo "CERT_HOSTS is empty in $ENV_FILE, fallback to DOMAIN=$DOMAIN"
  else
    echo "ERROR: CERT_HOSTS is empty in $ENV_FILE and DOMAIN is also empty" >&2
    exit 1
  fi
fi

declare -a HOSTS=()
IFS=',' read -r -a RAW_HOSTS <<< "$CERT_HOSTS"
for raw in "${RAW_HOSTS[@]}"; do
  host="$(echo "$raw" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$host" ]] && continue

  host="${host#http://}"
  host="${host#https://}"
  host="${host%%/*}"

  if [[ "$host" =~ : ]]; then
    if [[ "$host" =~ ^[^:]+:[0-9]+$ ]]; then
      host="${host%:*}"
    else
      echo "ERROR: unsupported host format in CERT_HOSTS: $host" >&2
      exit 1
    fi
  fi

  if [[ -n "$host" ]]; then
    HOSTS+=("$host")
  fi
done

if [[ "${#HOSTS[@]}" -eq 0 ]]; then
  echo "ERROR: no valid hosts parsed from CERT_HOSTS=$CERT_HOSTS" >&2
  exit 1
fi

CN="${HOSTS[0]}"
mkdir -p "$CERT_DIR"

TMP_OPENSSL_CONF="$(mktemp)"
cleanup() {
  rm -f "$TMP_OPENSSL_CONF"
}
trap cleanup EXIT

{
  echo "[ req ]"
  echo "default_bits       = 4096"
  echo "prompt             = no"
  echo "default_md         = sha256"
  echo "distinguished_name = dn"
  echo "x509_extensions    = v3_req"
  echo
  echo "[ dn ]"
  echo "CN = $CN"
  echo
  echo "[ v3_req ]"
  echo "subjectAltName = @alt_names"
  echo
  echo "[ alt_names ]"
} > "$TMP_OPENSSL_CONF"

dns_idx=1
ip_idx=1
for host in "${HOSTS[@]}"; do
  if [[ "$host" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "IP.$ip_idx = $host" >> "$TMP_OPENSSL_CONF"
    ip_idx=$((ip_idx + 1))
  else
    echo "DNS.$dns_idx = $host" >> "$TMP_OPENSSL_CONF"
    dns_idx=$((dns_idx + 1))
  fi
done

if [[ -f "$CERT_FILE" && -f "$KEY_FILE" ]] && openssl x509 -checkend 0 -noout -in "$CERT_FILE" >/dev/null 2>&1; then
  echo "Certificate exists and is still valid, reusing:"
  echo "  $CERT_FILE"
else
  echo "Generating self-signed certificate (valid ${CERT_DAYS} days):"
  echo "  CN=$CN"
  echo "  SAN=${HOSTS[*]}"
  openssl req -x509 -nodes -newkey rsa:4096 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -days "$CERT_DAYS" \
    -config "$TMP_OPENSSL_CONF" \
    -extensions v3_req

  chmod 600 "$KEY_FILE"
  chmod 644 "$CERT_FILE"
fi

if [[ "$SKIP_UP" -eq 1 ]]; then
  echo "Skip deploy requested (--skip-up)."
  exit 0
fi

docker compose \
  --project-name "$DEPLOY_PROJECT_NAME" \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  up -d --no-build

echo "Deployment complete for project: $DEPLOY_PROJECT_NAME"
