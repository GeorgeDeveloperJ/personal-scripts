import sys
import unittest
from unittest.mock import patch
import tempfile
import os
import time
from pathlib import Path

# test runner can discover the module
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from storage_sentinel import (
    get_mount_usage,
    send_notification,
    parse_args,
    classify_file,
    is_settled,
    scan_candidates,
    compute_fingerprint,
    resolve_destination_path,
)


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


class TestClassifyFiles(unittest.TestCase):
    def test_media_file(self):
        files = ["video.mp4", "movie.mkv", "clip.webm", "old.avi"]
        expected = Path("/mnt/data/Media")

        for file in files:
            got = classify_file(file, 1)
            self.assertEqual(got, expected)

    def test_iso_files(self):
        files = ["ubuntu.iso", "disk.img"]
        expected = Path("/mnt/data/ISOs")

        for file in files:
            got = classify_file(file, 1)
            self.assertEqual(got, expected)

    def test_archive_threshold(self):
        files = [
            ("backup.tar.gz", 150 * 1024**2),
            ("small.tar.gz", 50 * 1024**2),
            ("installer.deb", 120 * 1024**2),
            ("package.deb", 30 * 1024**2),
        ]

        for file in files:
            got = classify_file(file[0], file[1])
            if file[1] >= 100 * 1024**2:
                expected = Path("/mnt/data/Archives")
            else:
                expected = None

            self.assertEqual(got, expected)

    def test_ignored_files(self):
        ignoreds = [
            "video.mp4.crdownload",
            "file.part",
            "cache.tmp",
            ".hidden_movie.mkv",
            "main.py",
            "notes.txt",
            "data.csv",
        ]
        expected = None

        for ignored in ignoreds:
            got = classify_file(ignored, 1)
            self.assertEqual(got, expected)


class TestIsSettled(unittest.TestCase):
    def test_settled_case(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            file_path = dir_path / "test_artifact.txt"
            file_path.write_text("This is a temporary test file.")

            past_time = time.time() - 1200
            os.utime(file_path, (past_time, past_time))

            result = is_settled(file_path, min_age_seconds=900)

            self.assertTrue(result)

    def test_no_settled_case(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            file_path = dir_path / "test_artifact.txt"
            file_path.write_text("This is a temporary test file.")

            past_time = time.time() - 120
            os.utime(file_path, (past_time, past_time))

            result = is_settled(file_path, min_age_seconds=900)

            self.assertFalse(result)


class TestScanCandidates(unittest.TestCase):
    def test_scan_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            desktop = root / "Desktop"
            videos = root / "Videos"

            (desktop / "code_project").mkdir(parents=True)
            (videos / "series").mkdir(parents=True)

            top_mkv = desktop / "top.mkv"
            top_mkv.write_text("dummy")
            recent_mp4 = desktop / "recent.mp4"
            recent_mp4.write_text("dummy")
            nested_asset = desktop / "code_project" / "nested_asset.mkv"
            nested_asset.write_text("dummy")
            episode_mkv = videos / "series" / "episode.mkv"
            episode_mkv.write_text("dummy")

            past_time = time.time() - 1200
            for file in [top_mkv, nested_asset, episode_mkv]:
                os.utime(file, (past_time, past_time))

            intake_configs = [(desktop, False), (videos, True)]
            candidates = scan_candidates(intake_configs, min_age_seconds=900)

            candidates_path = [c[0] for c in candidates]

            self.assertIn(top_mkv, candidates_path)
            self.assertIn(episode_mkv, candidates_path)
            self.assertNotIn(recent_mp4, candidates_path)
            self.assertNotIn(nested_asset, candidates_path)


class TestFingerprintAndCollission(unittest.TestCase):
    def test_identical_files_same_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            file_path_1 = dir_path / "first_test_artifact.txt"
            file_path_2 = dir_path / "second_test_artifact.txt"
            file_path_1.write_text("This is a temporary test file.")
            file_path_2.write_text("This is a temporary test file.")

            same_fingerprint = compute_fingerprint(file_path_1) == compute_fingerprint(
                file_path_2
            )

            self.assertTrue(same_fingerprint)

    def test_different_files_different_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            file_path_1 = dir_path / "first_test_artifact.txt"
            file_path_2 = dir_path / "second_test_artifact.txt"
            file_path_1.write_text("This is a temporary test file.")
            file_path_2.write_text(
                "This is a temporary test file with different content."
            )

            same_fingerprint = compute_fingerprint(file_path_1) == compute_fingerprint(
                file_path_2
            )

            self.assertFalse(same_fingerprint)

    def test_large_file_head_tail_seeking(self):
        CHUNK_SIZE = 10
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            file_path_1 = dir_path / "first_test_artifact.txt"
            file_path_2 = dir_path / "second_test_artifact.txt"

            head_data = b"A" * CHUNK_SIZE
            middle_data = b"B" * CHUNK_SIZE
            tail_data_1 = b"C" * CHUNK_SIZE
            tail_data_2 = b"D" * CHUNK_SIZE

            file_path_1.write_bytes(head_data + middle_data + tail_data_1)
            file_path_2.write_bytes(head_data + middle_data + tail_data_2)

            fp1 = compute_fingerprint(file_path_1, CHUNK_SIZE)
            fp2 = compute_fingerprint(file_path_2, CHUNK_SIZE)

            self.assertNotEqual(fp1, fp2)

    def test_collission_resolver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            test_path = dir_path / "sample.mp4"

            no_exists_yet = resolve_destination_path(test_path)
            (test_path).touch()
            exists = resolve_destination_path(test_path)
            (dir_path / "sample (1).mp4").touch()
            repeated = resolve_destination_path(test_path)

            self.assertEqual(no_exists_yet, test_path)
            self.assertEqual(exists, dir_path / "sample (1).mp4")
            self.assertEqual(repeated, dir_path / "sample (2).mp4")


