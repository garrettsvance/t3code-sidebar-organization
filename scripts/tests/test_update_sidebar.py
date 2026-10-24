"""Exercise the updater with temporary repositories and fake application bundles."""

import sys
sys.dont_write_bytecode = True

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("update_sidebar", Path(__file__).parents[1] / "update-sidebar.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def bundle(path, marker, bundle_id=updater.BUNDLE_ID):
    (path / "Contents").mkdir(parents=True)
    with (path / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump({"CFBundleIdentifier": bundle_id}, stream)
    (path / "marker").write_text(marker)
    return path


class AppInstallationTests(unittest.TestCase):
    def test_success_retains_previous_app_and_leaves_data_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "new")
            data = root / "userdata"
            data.mkdir()
            (data / "chat").write_text("existing conversation")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
            with patch.object(updater, "run", side_effect=command):
                previous = updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "new")
            self.assertEqual((previous / "marker").read_text(), "old")
            self.assertEqual((data / "chat").read_text(), "existing conversation")

    def test_verification_failure_restores_installed_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "new")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
                if args[0] == "codesign" and args[-1] == app:
                    raise subprocess.CalledProcessError(1, "codesign")
            with patch.object(updater, "run", side_effect=command):
                with self.assertRaises(subprocess.CalledProcessError):
                    updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "old")

    def test_wrong_bundle_is_rejected_before_installed_app_is_moved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "wrong", "com.t3tools.t3code")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
            with patch.object(updater, "run", side_effect=command):
                with self.assertRaises(updater.UpdateError):
                    updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "old")


class ShutdownTests(unittest.TestCase):
    def test_open_app_prevents_installation_without_signalling_it(self):
        with patch.object(updater, "sidebar_is_running", return_value=True), patch.object(updater.os, "kill") as signal:
            with self.assertRaises(updater.UpdateError):
                updater.ensure_closed(Path("/unused"))
            signal.assert_not_called()

    def test_server_must_be_stopped_even_when_window_is_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "userdata").mkdir()
            (home / "userdata/server-runtime.json").write_text(json.dumps({"pid": 12345}))
            with patch.object(updater, "sidebar_is_running", return_value=False), patch.object(updater.os, "kill") as signal:
                with self.assertRaises(updater.UpdateError):
                    updater.ensure_closed(home)
                signal.assert_called_once_with(12345, 0)
            with patch.object(updater, "sidebar_is_running", return_value=False), patch.object(updater.os, "kill", side_effect=ProcessLookupError):
                updater.ensure_closed(home)


class PublishingTests(unittest.TestCase):
    def test_commits_and_pushes_source_and_stops_on_rejected_push(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote.git"
            repo = root / "checkout"
            upstream = root / "other-checkout"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "sidebar-test", str(repo)], check=True, capture_output=True)
            for key, value in (("user.name", "Updater Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
                updater.git(repo, "config", key, value)
            updater.git(repo, "remote", "add", "origin", str(remote))
            (repo / ".gitignore").write_text(".env.local\n")
            (repo / ".env.local").write_text("private fixture")
            (repo / "source.txt").write_text("first change")
            sha = updater.publish_source(repo, "sidebar-test", "feat: test update")
            self.assertEqual(updater.git(repo, "ls-remote", "origin", "refs/heads/sidebar-test").split()[0], sha)
            self.assertNotIn(".env.local", updater.git(repo, "ls-files").splitlines())
            self.assertEqual(updater.git(repo, "status", "--porcelain"), "")
            subprocess.run(["git", "clone", "-b", "sidebar-test", str(remote), str(upstream)], check=True, capture_output=True)
            for key, value in (("user.name", "Updater Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
                updater.git(upstream, "config", key, value)
            (upstream / "source.txt").write_text("remote update")
            updater.git(upstream, "commit", "-am", "remote change")
            updater.git(upstream, "push", "origin", "sidebar-test")
            (repo / "source.txt").write_text("local update")
            with self.assertRaises(subprocess.CalledProcessError):
                updater.publish_source(repo, "sidebar-test", "feat: local change")
            self.assertEqual((repo / "source.txt").read_text(), "local update")

    def test_source_changes_after_publish_are_detected(self):
        with patch.object(updater, "git", side_effect=["expected", " M source.txt"]):
            with self.assertRaises(updater.UpdateError):
                updater.require_clean_source(Path("/unused"), "expected")


class PipelineTests(unittest.TestCase):
    def test_push_failure_prevents_build_backup_and_install(self):
        with patch.object(sys, "argv", ["update-sidebar.py", "--message", "test"]), \
             patch.object(updater, "preflight", return_value="test"), \
             tempfile.TemporaryDirectory() as temp, \
             patch.object(updater, "SETUP", Path(temp)), \
             patch.object(updater, "publish_source", side_effect=updater.UpdateError("push failed")), \
             patch.object(updater, "build_app") as build, \
             patch.object(updater, "backup_data") as backup, \
             patch.object(updater, "install_app") as install:
            with self.assertRaises(updater.UpdateError):
                updater.main()
            build.assert_not_called()
            backup.assert_not_called()
            install.assert_not_called()

    def test_backup_failure_preserves_installed_app(self):
        with patch.object(sys, "argv", ["update-sidebar.py", "--message", "test"]), \
             patch.object(updater, "preflight", return_value="test"), \
             tempfile.TemporaryDirectory() as temp, \
             patch.object(updater, "SETUP", Path(temp)), \
             patch.object(updater, "publish_source", return_value="abc123"), \
             patch.object(updater, "build_app", return_value=Path(temp) / "prepared.app"), \
             patch.object(updater, "wait_for_close"), \
             patch.object(updater, "backup_data", side_effect=updater.UpdateError("backup failed")), \
             patch.object(updater, "install_app") as install:
            with self.assertRaises(updater.UpdateError):
                updater.main()
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
