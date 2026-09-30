#!/usr/bin/env bash

set -euo pipefail

THRESHOLD=80
percent=0

parse_args() {
  if [[ $# -eq 0 ]]; then
    return 0

  elif [[ $# -ge 1 && ("$1" == "-h" || "$1" == "--help") ]]; then
    print_help
    exit 0

  elif [[ $# -ge 2 && ("$1" == "-t" || "$1" == "--threshold") ]]; then
    if [[ ! "$2" =~ ^[0-9]+$ ]]; then
      echo "Error: Threshold must be a positive integer" >&2
      return 1
    fi

    THRESHOLD="$2"

  else
    echo "Invalid argument"
    print_help
    return 1

  fi
}

print_help() {
  echo "Disk Sentinel CLI"
  echo "Optional arguments:"
  echo "-t or --threshold (-t <number>): Sets the limit of percentage in use, defaults to 80"
  echo "example: -t 90"
}

check_disk() {
  percent=$(df -P / | awk 'NR==2 {print int($5)}')
}

check_percent() {
  if [[ ${percent} -le THRESHOLD ]]; then
    printf "OK: Disk usage is %d%%\n" "${percent}"
  else
    printf 'ALERT: Disk usage is %d%% (threshold: %d%%)\n' "${percent}" "${THRESHOLD}" >&2
    return 1
  fi
}

main() {
  echo "Starting Disk Sentinel..."
  parse_args "$@"
  check_disk
  check_percent
}

main "$@"
