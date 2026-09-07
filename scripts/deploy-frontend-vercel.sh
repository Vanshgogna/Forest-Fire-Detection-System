#!/usr/bin/env sh
set -eu

npm ci
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
