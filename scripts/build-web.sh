#!/bin/sh
# Build the static web copy of MakeShift for Cloudflare.
# The app lives under /makeshift on adipurohit.com, so files go in dist/makeshift/.
# Only the browser files ship. server.py, tests, and docs stay out.
set -e
OUT=dist/makeshift
rm -rf dist
mkdir -p "$OUT/vendor" "$OUT/recipes"
cp cube-mvp/index.html cube-mvp/app.js cube-mvp/parts.js cube-mvp/style.css "$OUT/"
cp cube-mvp/vendor/three.module.js cube-mvp/vendor/OrbitControls.js "$OUT/vendor/"
cp cube-mvp/recipes/pack.json "$OUT/recipes/"
echo "Built $OUT"
