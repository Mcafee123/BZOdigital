#!/bin/sh
set -eu

if [ ! -f package.json ]; then
  cat > package.json <<'EOF'
{
  "name": "enrichment",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "node --watch index.js",
    "start": "node index.js"
  }
}
EOF
fi

if [ ! -f index.js ]; then
  cat > index.js <<'EOF'
const port = Number(process.env.PORT || 3232);

console.log(`enrichment dev placeholder listening on ${port}`);
EOF
fi

exec "$@"
