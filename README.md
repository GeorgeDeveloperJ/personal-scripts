# Personal Scripts

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white)](https://kernel.org)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-standard--library-success.svg?style=for-the-badge)](https://docs.python.org/3/library/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A curated collection of lightweight developer utilities, system automation tools, and workflow scripts designed for Linux workstations. 

The primary utility featured in this repository is **Storage Sentinel**, a high-performance, zero-dependency storage monitor, deduplicator, and media triage daemon.

---

## About the Project

Workstations often suffer from partition bloat on primary NVMe drives due to incoming downloads, media captures, ISO images, and large development archives. **Personal Scripts** provides focused, reliable tools to automate workstation hygiene and data organization.

### Featured Tool: Storage Sentinel (`storage-sentinel.py`)

**Storage Sentinel** is an automated storage manager engineered to monitor NVMe drive health and migrate large static assets to secondary bulk storage devices (e.g., `/mnt/data`) safely and predictably.

#### Core Features
- **Partition Health Monitoring**: Inspects `/`, `/home`, and secondary mount usage using native filesystem metrics (`statvfs`), displaying an aligned tabular terminal report.
- **Desktop Alert Integration**: Dispatches native desktop notifications via `notify-send` whenever disk utilization crosses configured thresholds (default: 80%).
- **Settling & Transfer Protection**: Enforces an aging window (default: 15 minutes) and filters out active download extensions (`.crdownload`, `.part`, `.tmp`, `.swp`) to prevent moving files while writes are in progress.
- **Fast Fingerprint Deduplication**: Prevents storage duplication using a dual-chunk hashing algorithm (first 4 MB + last 4 MB via `blake2b`). Identical files are safely unlinked; distinct files with conflicting names receive non-destructive version suffixes (`(1)`).
- **Directory Traversal Safeguards**: Scans intake roots (`~/Desktop`) non-recursively to protect nested source-code repositories and project workspaces from asset stripping, while recursively triaging media directories (`~/Videos`).
- **Zero Third-Party Dependencies**: Written entirely in pure Python 3 standard library (`os`, `shutil`, `pathlib`, `hashlib`, `argparse`, `subprocess`). Requires no virtual environment or `pip` packages.

---

## Tech Stack

- **Runtime & Language**: Python 3.8+ (Standard Library only)
- **Filesystem & System APIs**: `os.statvfs`, `pathlib`, `shutil`
- **Hashing & Integrity**: `hashlib` (`blake2b` / `sha256`)
- **Desktop Integration**: `libnotify` (`notify-send`)
- **Daemon / Automation**: Native Linux `systemd --user` timers

---

## Getting Started

### Prerequisites

- A Linux-based operating system.
- **Python 3.8** or newer installed.
- `libnotify-bin` (optional, for desktop notification popups):
  ```bash
  # Debian / Ubuntu / Linux Mint
  sudo apt install libnotify-bin
  ```

### Installation

1. **Clone the repository:**
   ```bash
   git clone git@github.com:GeorgeDeveloperJ/personal-scripts.git
   cd personal-scripts
   ```

2. **Ensure executable permissions:**
   ```bash
   chmod +x python/storage-sentinel.py
   ```

3. **Symlink to your user binary path (recommended):**
   ```bash
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/python/storage-sentinel.py" ~/.local/bin/storage-sentinel
   ```
   *(Ensure `~/.local/bin` is present in your `$PATH`).*

---

## Usage

Storage Sentinel exposes an explicit, safety-first CLI interface:

### 1. Partition Health Report (`--report`)
Inspects capacity and usage across critical partitions with clear tabular alignment and desktop alerts if thresholds are breached:
```bash
storage-sentinel --report
```
*Custom threshold example:*
```bash
storage-sentinel --report --threshold 75.0
```

### 2. Simulation Mode (`--dry-run`)
Discovers eligible settled files across intake directories and outputs proposed migrations without touching the filesystem:
```bash
storage-sentinel --dry-run
```

### 3. Execution Mode (`--run`)
Performs active scanning, deduplication, and cross-device safe migration:
```bash
storage-sentinel --run
```

### Available Command-Line Options

| Flag | Short | Default | Description |
| :--- | :---: | :--- | :--- |
| `--run` | | `False` | Executes candidate scan, deduplication, and file moves. |
| `--dry-run` | | `False` | Simulates file discovery and prints proposed actions without modifying filesystem. |
| `--report` | | `False` | Prints partition capacity table and alerts on threshold violations. |
| `--threshold` | `-t` | `80.0` | Disk usage percentage threshold triggering alerts. |
| `--age` | `-a` | `900` | Minimum file settle age in seconds (15 minutes). |
| `--config` | `-c` | `~/.config/storage-sentinel/config.json` | Path to optional JSON configuration file. |

---

## Roadmap & Contributing

- [x] CLI core, argument parser, and action guards.
- [x] Partition health reporter (`statvfs`) and `notify-send` desktop warnings.
- [ ] Automated unit test suite (`unittest`) covering classifier, aging, and deduplication logic.
- [ ] Fast dual-chunk fingerprint deduplication engine.
- [ ] Systemd user service (`storage-sentinel.service`) and user timer (`storage-sentinel.timer`) units.
- [ ] Additional system maintenance and developer productivity scripts.

### Contributing
Contributions, suggestions, and feature requests are welcome!
1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feat/new-utility`).
3. Commit your Changes with Conventional Commits (`git commit -m 'feat: add network monitor utility'`).
4. Push to the Branch (`git push origin feat/new-utility`).
5. Open a Pull Request.

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.