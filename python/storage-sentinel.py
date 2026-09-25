#!/usr/bin/env python3

import argparse
import sys
import pathlib


def handle_args():
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

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if not (args.run or args.dry_run or args.report):
        parser.print_help()
        sys.exit(1)

    if args.run:
        handle_run(args)

    if args.dry_run:
        handle_dry_run(args)

    if args.report:
        handle_report(args)

def handle_run(args: argparse.Namespace):
    pass

def handle_dry_run(args: argparse.Namespace):
    pass


def handle_report(args: argparse.Namespace):
    pass


def main():
    handle_args()


if __name__ == "__main__":
    main()
