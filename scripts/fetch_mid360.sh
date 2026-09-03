#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
destination="$project_root/vendor/livox/mid-360-asm.stp"
mkdir -p "$(dirname "$destination")"
curl --fail --location --retry 3 --output "$destination.tmp" \
  'https://terra-1-g.djicdn.com/65c028cd298f4669a7f0e40e50ba1131/Mid360/mid-360-asm.stp'
mv "$destination.tmp" "$destination"
sha256sum "$destination"
