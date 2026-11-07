#!/bin/sh
# Build the static web copy of MakeShift for Cloudflare.
# The app lives under /makeshift on adipurohit.com, so files go in dist/makeshift/.
# Only the browser files ship. server.py, tests, and docs stay out.
set -e
OUT=dist/makeshift
rm -rf dist
mkdir -p "$OUT/vendor" "$OUT/recipes"
cp app/index.html app/app.js app/parts.js app/style.css "$OUT/"
cp app/vendor/three.module.js app/vendor/OrbitControls.js "$OUT/vendor/"
cp app/recipes/pack.json "$OUT/recipes/"
echo "Built $OUT"
