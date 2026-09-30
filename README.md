# Personal Scripts

[![Bash](https://img.shields.io/badge/bash-5.0+-green.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white)](https://kernel.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A curated collection of lightweight developer utilities, POSIX shell automations, and workflow scripts designed for Linux workstations.

---

## Utilities

### 1. Disk Sentinel (`bash/disk-sentinel.sh`)

A lightweight POSIX-compliant disk capacity monitor with configurable threshold alerting.

```bash
# Check primary partition usage (default 80% threshold)
./bash/disk-sentinel.sh

# Custom threshold
./bash/disk-sentinel.sh -t 90
```

### 2. Standard Script Template (`bash/template.sh`)

A robust starter template for bash scripts enforcing strict error handling (`set -euo pipefail`) and signal trap cleanup.

---

## Standalone Projects

- **[Storage Sentinel](https://github.com/GeorgeDeveloperJ/storage-sentinel)**: Automated zero-dependency Python media mover, dual-chunk BLAKE2b deduplicator, and partition triage daemon (migrated to its own dedicated repository).
