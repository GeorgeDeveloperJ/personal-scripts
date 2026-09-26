#!/usr/bin/env python3

import argparse
import sys
import pathlib
import os
import subprocess
import shutil


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


def handle_run(args: argparse.Namespace):
    pass


def handle_dry_run(args: argparse.Namespace):
    pass


def handle_report(args: argparse.Namespace):
    MOUNTS = ["/", "/home", "/mnt/data"]

    print("\n" + "=" * 65)
    print(" 🛡️  STORAGE SENTINEL — PARTITION HEALTH REPORT")
    print("=" * 65)
    print(f"{'Mount':<12} {'Used / Total':<20} {'Usage':<12} {'Free':<10}")
    print("-" * 65)

    warnings = []

    for mount in MOUNTS:
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
