#!/usr/bin/env python3

import argparse
from os.path import exists
from string.templatelib import Interpolation
import sys
from pathlib import Path
import os
import subprocess
import shutil
import time
from typing import Optional, Union
import hashlib
import json


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="storage Sentinel, powerful organizer script"
    )

    # Run Action Flag, Actual Scan
    parser.add_argument(
        "--run",
        action="store_true",
        help="triggers actual scan, triage, deduplication and move operations",
    )

    # Dry Run, Simulates, Doesn't touch Fs
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="simulates actions, and prints candidate file operations, without touching filesystem",
    )

    # Report, Checks partition health on / and /home
    parser.add_argument(
        "--report",
        action="store_true",
        help="checks partition health on / and /home, printing current usage and issuing a desktop",
    )

    # Path to JSON configuration file
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="~/.config/storage-sentinel/config.json",
        help="path to JSON configuration file",
    )

    # Mininum File Age
    parser.add_argument(
        "-a", "--age", type=int, default=900, help="minimun file age before moving"
    )

    # Disk Usage Threshold
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=80.0,
        help="disk usage percentage threshold triggering alerts",
    )
    args = parser.parse_args(argv)

    if not (args.run or args.dry_run or args.report):
        parser.print_help()
        sys.exit(1)

    return args


def handle_args():
    args = parse_args()

    if args.run:
        handle_run(args)

    elif args.dry_run:
        handle_dry_run(args)

    elif args.report:
        handle_report(args)


def get_mount_usage(path: str) -> dict:
    stat = os.statvfs(path)

    total_bytes = stat.f_blocks * stat.f_frsize
    free_bytes = stat.f_bavail * stat.f_frsize
    used_bytes = total_bytes - (stat.f_bfree * stat.f_frsize)
    percent_used = (1.0 - (stat.f_bavail / stat.f_blocks)) * 100.0

    return {
        "total_gb": round(total_bytes / (1024**3), 1),
        "free_gb": round(free_bytes / (1024**3), 1),
        "used_gb": round(used_bytes / (1024**3), 1),
        "percent_used": round(percent_used, 1),
    }


def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    try:
        notify = shutil.which("notify-send")
        if not notify:
            return
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "Storage-sentinel", title, message],
            check=True,
        )

    except FileNotFoundError:
        return


def classify_file(path: Union[str, Path], size_bytes: int) -> Optional[Path]:
    path = Path(path)

    IN_PROGRESS = (".crdownload", ".part", ".tmp", ".swp", ".download")
    MEDIA = (".mkv", ".mp4", ".avi", ".webm", ".flv", ".mov")
    ISO = (".iso", ".img")
    ARCHIVE = (".tar.gz", ".tar.xz", ".zip", ".7z", ".rar", ".deb", ".rpm", ".apk")
    SIZE_THRESHOLD = 100 * 1024**2

    is_ignored = path.name.startswith(".") or path.name.lower().endswith(IN_PROGRESS)

    if is_ignored:
        return None

    if path.suffix.lower() in MEDIA:
        return Path("/mnt/data/Media")

    if path.suffix in ISO:
        return Path("/mnt/data/ISOs")

    if path.name.lower().endswith(ARCHIVE) and size_bytes >= SIZE_THRESHOLD:
        return Path("/mnt/data/Archives")

    return None


def is_settled(path: Path, min_age_seconds: int = 900) -> bool:
    try:
        current_time = time.time()
        mtime = path.stat().st_mtime

        settled = (current_time - mtime) >= min_age_seconds

        return settled
    except FileNotFoundError:
        return False


def scan_candidates(intake_configs: list, min_age_seconds: int = 900) -> list:
    candidates = []
    for dir_path, is_recursive in intake_configs:
        dir_path = Path(dir_path).expanduser()
        if not dir_path.exists() or not dir_path.is_dir():
            continue
        if is_recursive:
            for item in dir_path.rglob("*"):
                if not item.is_file():
                    continue
                if not is_settled(item, min_age_seconds):
                    continue

                size = item.stat().st_size
                target_dir = classify_file(item, size)

                if target_dir is None:
                    continue

                candidates.append((item, target_dir, size))
        else:
            for item in dir_path.iterdir():
                if not item.is_file():
                    continue
                if not is_settled(item, min_age_seconds):
                    continue

                size = item.stat().st_size
                target_dir = classify_file(item, size)

                if target_dir is None:
                    continue

                candidates.append((item, target_dir, size))

    return candidates


def compute_fingerprint(path: Path, chunk_size: int = 4 * 1024**2) -> str:
    file_size = path.stat().st_size
    hasher = hashlib.blake2b()

    with open(path, "rb") as file:
        if file_size > 2 * chunk_size:
            head = file.read(chunk_size)
            hasher.update(head)

            file.seek(file_size - chunk_size)
            tail = file.read(chunk_size)
            hasher.update(tail)
        else:
            hasher.update(file.read())

    return hasher.hexdigest()


def resolve_destination_path(target_path: Path) -> Path:
    target_path = Path(target_path)
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    name = target_path.name

    compound_extensions = (".tar.gz", ".tar.xz", ".tar.bz2")

    stem = target_path.stem
    suffix = target_path.suffix

    if name.lower().endswith(compound_extensions):
        for ext in compound_extensions:
            if name.lower().endswith(ext):
                stem = name[: -len(ext)]
                suffix = ext
                break

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def migrate_candidates(candidates: list) -> None:
    for src, target_dir, size in candidates:
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / src.name

        if dest.exists():
            same_size = dest.stat().st_size == size
            same_fingerprint = compute_fingerprint(src) == compute_fingerprint(dest)
            if same_size and same_fingerprint:
                src.unlink()
                print(f"[DEDUPLICATED] Removed {src.name}")
                continue

            dest = resolve_destination_path(dest)

        shutil.move(src, dest)
        print(f"[MOVED] {src.name} -> {dest}")


def load_config(config_path: Union[str, Path]) -> dict:
    path = Path(config_path).expanduser()
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except (json.JSONDecodeError, OSError):
        print("[WARNING] Error decoding json, probably is a typo in JSON syntax")

    return {}


def handle_run(args: argparse.Namespace):
    config = load_config(args.config)

    if "intake_dirs" in config:
        intake_configs = [
            (Path(d["path"]), d.get("recursive", False)) for d in config["intake_dirs"]
        ]
    else:
        intake_configs = [
            (Path("~/Desktop"), False),
            (Path("~/Videos"), True),
            (Path("~/Downloads"), False),
        ]

    candidates = scan_candidates(intake_configs, min_age_seconds=args.age)

    if not candidates:
        print("No elegible files found for migration")
        handle_report(args)
        return

    migrate_candidates(candidates)

    handle_report(args)


def handle_dry_run(args: argparse.Namespace):
    config = load_config(args.config)

    if "intake_dirs" in config:
        intake_configs = [
            (Path(d["path"]), d.get("recursive", False)) for d in config["intake_dirs"]
        ]
    else:
        intake_configs = [
            (Path("~/Desktop"), False),
            (Path("~/Videos"), True),
            (Path("~/Downloads"), False),
        ]

    candidates = scan_candidates(intake_configs, min_age_seconds=args.age)

    if not candidates:
        print(
            "No eligible files found for migration (all files are clean or unsettled)"
        )
    else:
        print("\n" + "=" * 65)
        print(" 🛡️  STORAGE SENTINEL — DRY RUN SIMULATION")
        print("=" * 65)
        print(f"{'Target Category':<18} {'Size':<10} {'Candidate File':<35}")
        print("-" * 65)

        for src, target_dir, size in candidates:
            category = target_dir.name
            size_str = (
                f"{size / (1024**3):>5.1f} GB"
                if size >= 1024**3
                else f"{size / (1024**2):>5.1f} MB"
            )
            print(f"{category:<18} {size_str:<10} {src.name:<35}")

        print("-" * 65)
        total_volume = round(sum(c[2] for c in candidates) / (1024**3), 1)
        print(f"Total: {len(candidates)} files  |  Total Volume: {total_volume} GB")
        print("ℹ️  Simulation mode: zero filesystem modifications performed.")
        print("=" * 65 + "\n")


def handle_report(args: argparse.Namespace):
    config = load_config(args.config)
    mounts = config.get("mounts", ["/", "/home", "/mnt/data"])

    print("\n" + "=" * 65)
    print(" 🛡️  STORAGE SENTINEL — PARTITION HEALTH REPORT")
    print("=" * 65)
    print(f"{'Mount':<12} {'Used / Total':<20} {'Usage':<12} {'Free':<10}")
    print("-" * 65)

    warnings = []

    for mount in mounts:
        if not os.path.exists(mount):
            continue

        mount_usage = get_mount_usage(mount)
        used_val = f"{mount_usage['used_gb']:>5.1f}G"
        total_val = f"{mount_usage['total_gb']:>6.1f}G"
        used_str = f"{used_val} / {total_val}"
        percent_str = f"[{mount_usage['percent_used']:>5.1f}%]"
        free_str = f"{mount_usage['free_gb']:>6.1f}G"

        print(f"{mount:<12} {used_str:<20} {percent_str:<12} {free_str:<10}")

        if mount_usage["percent_used"] >= args.threshold:
            warnings.append((mount, mount_usage["percent_used"]))
            send_notification(
                title="Storage Sentinel Alert",
                message=f"Storage alert: {mount} is at {mount_usage['percent_used']}% (threshold: {args.threshold}%)",
                urgency="critical",
            )

    print("=" * 65)

    if warnings:
        print("\n⚠️  ALERTS TRIGGERED:")
        for mount, pct in warnings:
            print(f"  • {mount} is at {pct}% (exceeded {args.threshold}% threshold)")
    else:
        print("\n✅ All partitions healthy.")
    print()


def main():
    handle_args()


if __name__ == "__main__":
    main()
