#!/usr/bin/env bash

set -euo pipefail

cleanup() {
  echo "Executing emergency cleanup..."
  if [[ -n "${temp_dir:-}" && -d "${temp_dir}" ]]; then
    rm -rf "${temp_dir}"
  fi

}

main() {
  echo "Environment and Temporary Dir are ready"
}

temp_dir=$(mktemp -d)

trap cleanup EXIT INT TERM

main "$@"
