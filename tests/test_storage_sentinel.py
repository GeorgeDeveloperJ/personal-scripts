import sys
import unittest
from unittest.mock import patch
import tempfile
import os
import time
from pathlib import Path

# test runner can discover the module
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from storage_sentinel import get_mount_usage, send_notification, parse_args


class TestGetMountUsage(unittest.TestCase):
    def test_get_mount_usage_valid_path(self):
        mount_usage = get_mount_usage("/")
        required_keys = ["total_gb", "used_gb", "free_gb", "percent_used"]
        for key in required_keys:
            self.assertIn(key, mount_usage)

        self.assertTrue(mount_usage["total_gb"] > 0)

        self.assertTrue(0.0 <= mount_usage["percent_used"] <= 100.0)

        self.assertTrue(mount_usage["used_gb"] <= mount_usage["total_gb"])

        self.assertTrue(mount_usage["free_gb"] <= mount_usage["total_gb"])


class TestSendNotification(unittest.TestCase):
    @patch("storage_sentinel.subprocess.run")
    @patch("storage_sentinel.shutil.which")
    def test_send_notification_success(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/notify-send"

        send_notification("Alert Title", "Low Space", urgency="critical")

        mock_run.assert_called_once_with(
            [
                "notify-send",
                "-u",
                "critical",
                "-a",
                "Storage-sentinel",
                "Alert Title",
                "Low Space",
            ],
            check=True,
        )

    @patch("storage_sentinel.subprocess.run")
    @patch("storage_sentinel.shutil.which")
    def test_send_notification_headless_graceful(self, mock_which, mock_run):
        mock_which.return_value = None

        send_notification("Alert", "Msg")

        mock_run.assert_not_called()


class TestCLIArguments(unittest.TestCase):
    def test_default_arguments(self):
        argv = ["--report"]

        args = parse_args(argv)

        self.assertTrue(args.age == 900)
        self.assertTrue(args.threshold == 80.0)
        self.assertTrue(args.report)

    def test_custom_arguments(self):
        argv = ["--run", "-a", "1800", "-t", "90.0"]

        args = parse_args(argv)

        self.assertTrue(args.age == 1800)
        self.assertTrue(args.threshold == 90.0)
        self.assertTrue(args.run)

    @patch("storage_sentinel.argparse.ArgumentParser.print_help")
    def test_no_action_flag(self, mock_help):
        argv = ["-a", "500"]

        with self.assertRaises(SystemExit) as cm:
            parse_args(argv)

        mock_help.assert_called_once()
        self.assertEqual(cm.exception.code, 1)

    @patch("storage_sentinel.argparse.ArgumentParser.print_help")
    def test_empty_invocation(self, mock_help):
        argv = []

        with self.assertRaises(SystemExit) as cm:
            parse_args(argv)

        mock_help.assert_called_once()
        self.assertEqual(cm.exception.code, 1)
