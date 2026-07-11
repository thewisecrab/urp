#!/usr/bin/env sh
set -eu

output=".env"
if [ -e "$output" ] && [ "${1:-}" != "--force" ]; then
  printf '%s\n' ".env already exists; pass --force to replace it" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  printf '%s\n' "openssl is required to generate local development secrets" >&2
  exit 1
fi

umask 077
api_key=$(openssl rand -hex 32)
postgres_password=$(openssl rand -hex 32)

{
  printf '%s\n' "# Generated for local URP development. Do not commit this file."
  printf '%s\n' "URP_MODE=observe"
  printf '%s\n' "URP_LOCAL_API_KEY=$api_key"
  printf '%s\n' "URP_POSTGRES_PASSWORD=$postgres_password"
} > "$output"

printf '%s\n' "Wrote private local development credentials to .env"
