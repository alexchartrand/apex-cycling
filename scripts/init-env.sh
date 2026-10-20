#!/bin/bash
# Create .env.prod from .env.prod.example with fresh random secrets.
#
#   scripts/init-env.sh <domain> <letsencrypt-email>
#
# Refuses to overwrite an existing .env.prod (rotating JWT_SECRET signs
# everyone out, a new DATA_ENCRYPTION_KEY orphans stored connections; changing POSTGRES_PASSWORD here would not change the database).
set -euo pipefail
cd "$(dirname "$0")/.."

[ $# -eq 2 ] || { echo "usage: $0 <domain> <letsencrypt-email>" >&2; exit 2; }
[ ! -e .env.prod ] || { echo ".env.prod already exists, not touching it" >&2; exit 1; }

domain=$1
email=$2
jwt=$(openssl rand -hex 32)
data_key=$(openssl rand -base64 32 | tr '+/' '-_')
pg=$(openssl rand -hex 24)

umask 077
sed -e "s|^DOMAIN=.*|DOMAIN=$domain|" \
    -e "s|^ACME_EMAIL=.*|ACME_EMAIL=$email|" \
    -e "s|^JWT_SECRET=.*|JWT_SECRET=$jwt|" \
    -e "s|^DATA_ENCRYPTION_KEY=.*|DATA_ENCRYPTION_KEY=$data_key|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$pg|" \
    .env.prod.example > .env.prod

echo "Wrote .env.prod (mode 600). Review the optional SMTP / backup settings in it."
